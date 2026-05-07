"""
Modulo processor.py contiene la classe AudioProcessor, destinata al pre-processing dei file audio
prima del loro utilizzo nei sistemi di riconoscimento vocale. La classe fornisce metodi per la
conversione in WAV a 16 kHz, la normalizzazione del livello, l'aggiunta di silenzio all'inizio della
registrazione e la rimozione dei file temporanei creati durante l'elaborazione.
"""

import os
import subprocess
from typing import Dict, Tuple
import logging

from ..infrastructure.storage import create_temp_file, cleanup_temp_files

logger = logging.getLogger('app.audio_processor')


class AudioProcessor:
    """
    Classe per il pre-processing dei file audio prima del riconoscimento.

    Attributes:
        config (Dict): Dizionario con i parametri di configurazione.
        norm_level (str): Livello di normalizzazione audio.
        compand_params (str): Parametri di compressione audio.
    """
    
    def __init__(self, config: Dict):
        """
        Inizializzazione del processore audio.

        Args:
            config: Dizionario con i parametri di configurazione.
        """
        self.config = config
        self.norm_level = config.get("norm_level", "-0.5")
        self.compand_params = config.get("compand_params", "0.3,1 -90,-90,-70,-70,-60,-20,0,0 -5 0 0.2")

    def convert_to_wav(self, input_path: str) -> str:
        """
        Conversione del file audio in formato WAV con frequenza di campionamento 16 kHz (mono).

        Args:
            input_path: Percorso del file audio di input.

        Returns:
            Percorso del file WAV convertito.

        Raises:
            subprocess.CalledProcessError: Se si verifica un errore durante la conversione.
        """
        audio_rate = self.config["audio_rate"]

        # Creiamo un file temporaneo per il WAV
        output_path = create_temp_file(".wav")
        
        # Comando per la conversione
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
            "-y",
            "-i", input_path,
            "-ar", f"{audio_rate}",
            "-ac", "1",  # Audio mono
            output_path
        ]
        
        logger.debug("Conversione in WAV: %s", " ".join(cmd))
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info("File convertito in WAV: %s", output_path)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error("Errore durante la conversione in WAV: %s", e.stderr.decode())
            raise
    
    def normalize_audio(self, input_path: str) -> str:
        """
        Normalizzazione del file audio utilizzando sox.

        Args:
            input_path: Percorso al file WAV.

        Returns:
            Percorso al file WAV normalizzato.

        Raises:
            subprocess.CalledProcessError: Se si verifica un errore durante la normalizzazione.
        """
        # Creiamo un file temporaneo per l'audio normalizzato
        output_path = create_temp_file("_normalized.wav")
        
        # Comando per normalizzare l'audio con sox
        cmd = [
            "sox", 
            input_path, 
            output_path, 
            "norm", self.norm_level,
            "compand"
        ] + self.compand_params.split()
        
        logger.debug("Normalizzazione audio: %s", " ".join(cmd))
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info("Audio normalizzato: %s", output_path)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error("Errore durante la normalizzazione audio: %s", e.stderr.decode())
            raise
    
    def add_silence(self, input_path: str) -> str:
        """
        Aggiunge silenzio all'inizio del file audio.

        Args:
            input_path: Percorso al file audio.

        Returns:
            Percorso al file audio con silenzio aggiunto.

        Raises:
            subprocess.CalledProcessError: Se si verifica un errore durante l'aggiunta del silenzio.
        """
        # Creiamo un file temporaneo
        output_path = create_temp_file("_silence.wav")
        
        cmd = [
            "sox",
            input_path,
            output_path,
            "pad", "2.0", "1.0"  # Aggiunta di silenzio all'inizio e alla fine (secondi)
        ]
        
        logger.info("Aggiunta silenzio: %s", " ".join(cmd))
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info("Silenzio aggiunto: %s", output_path)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error("Errore durante l'aggiunta del silenzio: %s", e.stderr.decode())
            raise
    
    def process_audio(self, input_path: str) -> Tuple[str, list]:
        """
        Elaborazione completa del file audio: conversione, normalizzazione e aggiunta di silenzio.

        Args:
            input_path: Percorso al file audio di input.

        Returns:
            Tupla: (percorso al file elaborato, lista dei file temporanei da eliminare)

        Raises:
            Exception: Se si verifica un errore durante l'elaborazione audio.
        """
        temp_files = []
        
        try:
            # Conversione in WAV
            wav_path = self.convert_to_wav(input_path)
            if wav_path != input_path:  # Se è stato creato un file temporaneo
                temp_files.append(wav_path)
            
            # Normalizzazione
            normalized_path = self.normalize_audio(wav_path)
            temp_files.append(normalized_path)

            # Aggiunta di silenzio
            silence_path = self.add_silence(normalized_path)
            temp_files.append(silence_path)
            
            return silence_path, temp_files
        
        except Exception as e:
            logger.error("Errore durante l'elaborazione audio %s: %s", input_path, e)
            cleanup_temp_files(temp_files)
            raise