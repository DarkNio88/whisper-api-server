"""
Il modulo transcriber.py contiene la classe WhisperTranscriber, che utilizza il modello Whisper di
OpenAI per trascrivere file audio in testo. La classe include metodi per il caricamento del modello,
il processamento dell'audio (tramite AudioProcessor) e l'esecuzione della trascrizione.
Gestisce la selezione del dispositivo (CPU, CUDA, MPS) per i calcoli e offre il supporto a
Flash Attention 2 per accelerare il modello su GPU compatibili.
"""

import time
import threading
import traceback
from typing import Dict, Tuple, Union
import logging

import numpy as np
import torch
from transformers import (
    WhisperForConditionalGeneration,
    WhisperProcessor,
    pipeline,
)

from ..audio.processor import AudioProcessor
from ..audio.utils import load_audio
from ..infrastructure.storage import cleanup_temp_files

logger = logging.getLogger('app.transcriber')


class WhisperTranscriber:
    """
    Classe per il riconoscimento vocale tramite il modello Whisper.

    Attributes:
        config (Dict): Dizionario con i parametri di configurazione.
        model_path (str): Percorso del modello Whisper.
        language (str): Lingua di riconoscimento.
        chunk_length_s (int): Lunghezza del chunk audio in secondi.
        batch_size (int): Dimensione del batch per l'elaborazione.
        max_new_tokens (int): Numero massimo di nuovi token per la generazione.
        return_timestamps (bool): Flag per restituire i timestamp.
        temperature (float): Parametro di temperatura per la generazione.
        torch_dtype (torch.dtype): Tipo dati ottimale per i tensori.
        audio_processor (AudioProcessor): Oggetto per il processamento audio.
        device (torch.device): Dispositivo per i calcoli.
        model (WhisperForConditionalGeneration): Modello Whisper caricato.
        processor (WhisperProcessor): Processor per il modello Whisper.
        asr_pipeline (pipeline): Pipeline per il riconoscimento automatico del parlato.
    """
    
    def __init__(self, config: Dict):
        """
        Inizializzazione del transcriber.

        Args:
            config: Dizionario con i parametri di configurazione.
        """
        self.config = config
        self.model_path = config["model_path"]
        self.language = config["language"]
        self.chunk_length_s = config["chunk_length_s"]
        self.batch_size = config["batch_size"]
        self.max_new_tokens = config["max_new_tokens"]
        self.return_timestamps = config["return_timestamps"]
        self.temperature = config["temperature"]

        # Lock per l'accesso thread-safe al modello —
        # Waitress serve richieste in più thread,
        # mentre la pipeline di HuggingFace non è thread-safe
        self._inference_lock = threading.Lock()

        # Creiamo l'oggetto per l'elaborazione audio
        self.audio_processor = AudioProcessor(config)

        # Determiniamo il dispositivo per i calcoli
        self.device = self._get_device()

        # Tipo dati ottimale per i tensori (dipende dal dispositivo)
        self.torch_dtype = self._get_torch_dtype()

        # Carichiamo il modello durante l'inizializzazione
        self._load_model()

    def _get_device(self) -> torch.device:
        """
        Determina il dispositivo disponibile per i calcoli.

        Returns:
            Oggetto dispositivo di PyTorch.
        """
        if torch.cuda.is_available():
            # Otteniamo device_id dalla configurazione, default 0
            device_id = self.config.get("device_id", 0)
            
            # Controlliamo che device_id sia un intero
            if not isinstance(device_id, int):
                logger.warning("device_id dovrebbe essere un intero, ottenuto: %s. Uso del valore predefinito 0", device_id)
                device_id = 0
            
            # Verifichiamo se il GPU richiesto è disponibile
            device_count = torch.cuda.device_count()
            if device_id >= device_count:
                logger.warning("GPU richiesto con indice %s non disponibile. GPU disponibili: %s. Uso GPU indice 0", device_id, device_count)
                device_id = 0
            
            logger.info("Usando CUDA GPU con indice %s per i calcoli", device_id)
            return torch.device(f"cuda:{device_id}")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            logger.info("Usando MPS (Apple Silicon) per i calcoli")
            # Workaround per MPS: PyTorch verifica is_initialized()
            # quando si creano tensori su dispositivo MPS, il che può causare errori
            # in modalità monoprocesso.
            # TODO: Rimuovere dopo l'aggiornamento a PyTorch >= 2.5
            setattr(torch.distributed, "is_initialized", lambda: False)
            return torch.device("mps")
        else:
            logger.info("Usando CPU per i calcoli")
            return torch.device("cpu")

    def _get_torch_dtype(self) -> torch.dtype:
        """
        Determina il tipo dati ottimale per i tensori in base al dispositivo.

        Returns:
            torch.float32 per CPU, torch.bfloat16 per GPU/MPS.
        """
        if self.device.type == "cpu":
            return torch.float32
        return torch.bfloat16

    def _load_model(self) -> None:
        """
        Caricamento del modello e del processor.

        Raises:
            Exception: Se non è stato possibile caricare il modello.
        """
        logger.info("Caricamento del modello da %s", self.model_path)

        model_kwargs = dict(
            torch_dtype=self.torch_dtype,
            low_cpu_mem_usage=True,
            use_safetensors=True,
        )

        use_flash_attn = False
        if self.device.type == "cuda":
            # Flash Attention 2 richiede architettura Ampere o successiva (compute capability >= 8.0)
            capability = torch.cuda.get_device_capability(self.device.index)
            if capability[0] >= 8:
                use_flash_attn = True
                logger.info("GPU supporta Flash Attention 2 (compute capability: %d.%d)", *capability)
            else:
                logger.info("GPU non supporta Flash Attention 2 (compute capability: %d.%d), uso modalità standard", *capability)

        try:
            if use_flash_attn:
                model_kwargs["attn_implementation"] = "flash_attention_2"
            self.model = WhisperForConditionalGeneration.from_pretrained(
                self.model_path, **model_kwargs
            ).to(self.device)
            if use_flash_attn:
                logger.info("Utilizzo di Flash Attention 2")
        except Exception as e:
            logger.warning("Impossibile caricare il modello con Flash Attention: %s", e)
            model_kwargs.pop("attn_implementation", None)
            self.model = WhisperForConditionalGeneration.from_pretrained(
                self.model_path, **model_kwargs
            ).to(self.device)

        self.processor = WhisperProcessor.from_pretrained(self.model_path)

        self.asr_pipeline = pipeline(
            "automatic-speech-recognition",
            model=self.model,
            tokenizer=self.processor.tokenizer,
            feature_extractor=self.processor.feature_extractor,
            chunk_length_s=self.chunk_length_s,
            batch_size=self.batch_size,
            return_timestamps=self.return_timestamps,
            torch_dtype=self.torch_dtype,
            device=self.device,
        )

        logger.info("Modello caricato con successo e pronto all'uso")

    def transcribe(self, audio_path: str, return_timestamps: bool = None,
                   language: str = None, temperature: float = None,
                   prompt: str = None) -> Union[str, Dict]:
        """
        Trascrizione del file audio.

        Args:
            audio_path: Percorso del file audio processato.
            return_timestamps: Flag per restituire i timestamp. Se None — preso dalla configurazione.
            language: Lingua del riconoscimento. Se None — presa dalla configurazione.
            temperature: Parametro di temperatura per la generazione. Se None — preso dalla configurazione.
            prompt: Prompt testuale per il modello (nomi, termini, contesto).

        Returns:
            A seconda del valore di return_timestamps:
            - Se return_timestamps=False: stringa con il testo riconosciuto
            - Se return_timestamps=True: dizionario con chiavi "segments" (lista di dizionari con chiavi start_time_ms, end_time_ms, text) e "text" (testo completo)
        """
        if return_timestamps is None:
            return_timestamps = self.return_timestamps
        if language is None:
            language = self.language
        if temperature is None:
            temperature = self.temperature

        logger.info("Inizio trascrizione del file: %s", audio_path)

        try:
            # Caricamento dell'audio come array numpy
            audio_array, sampling_rate = load_audio(audio_path, sr=16000)

            # Trascrizione con il formato dati corretto
            generate_kwargs = {
                "language": language,
                "max_new_tokens": self.max_new_tokens,
                "temperature": temperature,
            }
            if prompt:
                generate_kwargs["prompt_ids"] = self.processor.get_prompt_ids(
                    prompt, return_tensors="pt"
                ).to(self.device)

            with self._inference_lock:
                result = self.asr_pipeline(
                    {"raw": audio_array, "sampling_rate": sampling_rate},
                    generate_kwargs=generate_kwargs,
                    return_timestamps=return_timestamps,
                )
            
                # Se i timestamp non sono richiesti, restituiamo solo il testo
                if not return_timestamps:
                    transcribed_text = result.get("text", "")
                    logger.info("Trascrizione completata: ottenuti %s caratteri di testo", len(transcribed_text))
                    return transcribed_text
            
            # Se i timestamp sono stati richiesti, processiamo e formattiamo il risultato
            segments = []
            full_text = result.get("text", "")
            
            if "chunks" in result:
                # Per le nuove versioni del modello Whisper
                for chunk in result["chunks"]:
                    start_time = chunk.get("timestamp", [0, 0])[0]
                    end_time = chunk.get("timestamp", [0, 0])[1]
                    text = chunk.get("text", "").strip()
                    
                    segments.append({
                        "start_time_ms": int(start_time * 1000),
                        "end_time_ms": int(end_time * 1000),
                        "text": text
                    })
            elif hasattr(result, "get") and "segments" in result:
                # Per le vecchie versioni del modello Whisper
                for segment in result["segments"]:
                    start_time = segment.get("start", 0)
                    end_time = segment.get("end", 0)
                    text = segment.get("text", "").strip()
                    
                    segments.append({
                        "start_time_ms": int(start_time * 1000),
                        "end_time_ms": int(end_time * 1000),
                        "text": text
                    })
            else:
                logger.warning("Timestamp richiesti, ma non trovati nel risultato della trascrizione")
            
            logger.info("Trascrizione con timestamp completata: ottenuti %s segmenti", len(segments))
            
            # Restituiamo il dizionario con i segmenti e il testo completo
            return {
                "segments": segments,
                "text": full_text
            }
            
        except Exception as e:
            logger.error("Errore durante la trascrizione del file audio '%s': %s", audio_path, e)
            logger.error("Tipo di eccezione: %s", type(e).__name__)
            logger.error("Traceback: %s", traceback.format_exc())
            raise

    def process_file(self, input_path: str, return_timestamps: bool = None,
                     language: str = None, temperature: float = None,
                     prompt: str = None) -> Union[str, Dict]:
        """
        Processo completo di elaborazione e trascrizione di un file audio.

        Args:
            input_path: Percorso del file audio sorgente.
            return_timestamps: Flag per restituire i timestamp. Se None — preso dalla configurazione.
            language: Lingua del riconoscimento. Se None — presa dalla configurazione.
            temperature: Parametro di temperatura per la generazione. Se None — preso dalla configurazione.
            prompt: Prompt testuale per il modello (nomi, termini, contesto).

        Returns:
            A seconda del valore di return_timestamps:
            - Se return_timestamps=False: stringa con il testo riconosciuto
            - Se return_timestamps=True: dizionario con chiavi "segments" e "text"
        """
        start_time = time.time()
        logger.info("Inizio elaborazione del file: %s", input_path)
        
        temp_files = []
        
        try:
            # Elaborazione audio (conversione, normalizzazione, aggiunta silenzio)
            processed_path, temp_files = self.audio_processor.process_audio(input_path)
            
            # Trascrizione
            result = self.transcribe(processed_path, return_timestamps=return_timestamps,
                                     language=language, temperature=temperature,
                                     prompt=prompt)
            
            elapsed_time = time.time() - start_time
            logger.info("Elaborazione e trascrizione completate in %.2f secondi", elapsed_time)
            
            return result
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error("Errore durante l'elaborazione del file '%s' dopo %.2f secondi: %s", input_path, elapsed_time, e)
            logger.error("Tipo di eccezione: %s", type(e).__name__)
            logger.error("Traceback: %s", traceback.format_exc())
            raise
            
        finally:
            # Pulizia dei file temporanei
            cleanup_temp_files(temp_files)