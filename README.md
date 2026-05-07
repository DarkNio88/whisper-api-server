# Server API per Whisper

Servizio API locale, compatibile con OpenAI, per il riconoscimento vocale basato sul modello Whisper. Questo servizio offre un modo semplice per trascrivere file audio in vari formati con elevata accuratezza ed è progettato per essere compatibile con l'API OpenAI Whisper.

![Client Interface](client.png)

## Caratteristiche

- 🔊 Riconoscimento vocale di alta qualità con i modelli Whisper
- 🌐 Endpoint API compatibili con OpenAI
- 🚀 Supporto per accelerazione hardware (CUDA, MPS)
- ⚡ Flash Attention 2 per trascrizioni più rapide su GPU compatibili
- 🎛️ Pre-elaborazione audio per risultati di trascrizione migliori
- 🔄 Più metodi di input (upload file, URL, base64, file locali)
- 📊 Generazione opzionale di timestamp per l'allineamento a livello di parola
- 🎧 Comodo client integrato con modifica del testo e riproduzione audio
- 📱 Interfaccia web responsive inclusa
- 📝 Salvataggio storico delle trascrizioni

## Requisiti

- Python 3.12+ consigliato
- GPU compatibile con CUDA (opzionale, per prestazioni migliori)
- FFmpeg e SoX per l'elaborazione audio
- Modello Whisper (scaricabile da Hugging Face)

## Installazione

### Usando `server.sh` (consigliato)

1. Clona il repository:
```bash
git clone https://github.com/DarkNio88/whisper-api-server.git
cd whisper-api-server
```

2. Esegui lo script del server con il flag `--update` per creare e configurare l'ambiente conda:
```bash
chmod +x server.sh
./server.sh --update
```

Questo:
- creerà un ambiente conda chiamato "whisper-api" con Python 3.12
- installerà tutte le dipendenze richieste
- avvierà il servizio

### Installazione manuale

1. Crea e attiva un ambiente conda:
```bash
conda create -n whisper-api python=3.12
conda activate whisper-api
```

2. Installa le dipendenze richieste:
```bash
pip install -r requirements.txt
```

3. Avvia il servizio:
```bash
python server.py
```

## Configurazione

Il servizio è configurato tramite il file `config.json`:

```json
{
    "service_port": 5042,
    "model_path": "whisper/model",
    "language": "italian",
    "enable_history": true,
    "max_history_days": 30,
    "chunk_length_s": 28,
    "batch_size": 6,
    "max_new_tokens": 384,
    "temperature": 0.01,
    "return_timestamps": false,
    "audio_rate": 16000,
    "norm_level": "-0.55",
    "compand_params": "0.3,1 -90,-90,-70,-50,-40,-15,0,0 -7 0 0.15",
    "device_id": 0,
    "file_validation": {
        "max_file_size_mb": 500,
        "allowed_extensions": [".wav", ".mp3", ".ogg", ".flac", ".m4a", ".oga", ".aac", ".webm"],
        "allowed_mime_types": ["audio/wav", "audio/mpeg", "audio/ogg", "audio/flac", "audio/mp4", "audio/x-m4a", "audio/aac", "audio/webm"]
    },
    "log_level": "INFO",
    "log_file": "logs/whisper_api.log",
    "request_logging": {
        "exclude_endpoints": ["/health", "/static"]
    }
}
```

### Parametri di configurazione

| Parameter | Descrizione |
|-----------|-------------|
| `service_port` | Porta su cui girerà il servizio |
| `model_path` | Percorso alla directory del modello Whisper |
| `language` | Lingua per la trascrizione (es. "russian", "english", "italian", ecc.) |
| `enable_history` | Se salvare la cronologia delle trascrizioni (true/false) |
| `max_history_days` | Numero di giorni per cui mantenere la cronologia prima della rotazione |
| `chunk_length_s` | Lunghezza dei chunk audio per l'elaborazione (in secondi) |
| `batch_size` | Dimensione del batch per l'elaborazione |
| `max_new_tokens` | Massimo numero di nuovi token per l'output del modello |
| `temperature` | Parametro di temperatura del modello (valori bassi = più deterministico) |
| `return_timestamps` | Se restituire i timestamp nella trascrizione |
| `audio_rate` | Frequenza di campionamento dell'audio in Hz |
| `norm_level` | Livello di normalizzazione per la pre-elaborazione audio |
| `compand_params` | Parametri per compressione/espansione audio |
| `device_id` | Indice del dispositivo CUDA da usare per l'inferenza |
| `file_validation.max_file_size_mb` | Dimensione massima del file ammessa in megabyte |
| `file_validation.allowed_extensions` | Elenco delle estensioni audio accettate |
| `file_validation.allowed_mime_types` | Elenco dei MIME-type accettati |
| `log_level` | Livello di logging (DEBUG, INFO, WARNING, ERROR) |
| `log_file` | Percorso del file di log |
| `request_logging.exclude_endpoints` | Endpoint esclusi dalla registrazione delle richieste |

## Interfaccia web

L'interfaccia web è accessibile a:
```
http://localhost:5042/
```

L'interfaccia permette di:
- Caricare file audio via drag-and-drop o selettore file
- Caricare più file per l'elaborazione sequenziale
- Ascoltare l'audio caricato
- Modificare il testo della trascrizione se necessario
- Scaricare i risultati come TXT o JSON oppure copiarli negli appunti
- Visualizzare i dettagli delle richieste/risposte API per il debug

## Uso dell'API

### Controllo di stato (Health check)

```bash
curl http://localhost:5042/health
```

### Ottenere la configurazione

```bash
curl http://localhost:5042/config
```

### Ottenere i modelli disponibili

```bash
curl http://localhost:5042/v1/models
```

### Trascrivere un file audio (compatibile OpenAI)

```bash
curl -X POST http://localhost:5042/v1/audio/transcriptions \
  -F file=@audio.mp3
```

### Trascrivere da URL

```bash
curl -X POST http://localhost:5042/v1/audio/transcriptions/url \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/audio.mp3"}'
```

### Trascrivere da base64

```bash
curl -X POST http://localhost:5042/v1/audio/transcriptions/base64 \
  -H "Content-Type: application/json" \
  -d '{"file":"base64_encoded_audio_data"}'
```

### Trascrizione asincrona

Invia un file per la trascrizione in background e ricevi un ID task:

```bash
curl -X POST http://localhost:5042/v1/audio/transcriptions/async \
  -F file=@audio.mp3
```

Risposta:
```json
{"task_id": "abc123..."}
```

### Ottenere lo stato di un task asincrono

```bash
curl http://localhost:5042/v1/tasks/<task_id>
```

Risposta quando completato:
```json
{"task_id": "abc123...", "status": "completed", "result": {...}}
```

Stati possibili: `pending`, `completed`, `failed`.

### Richiesta con parametri aggiuntivi

```bash
curl -X POST http://localhost:5042/v1/audio/transcriptions \
  -F file=@audio.mp3 \
  -F language=english \
  -F return_timestamps=true \
  -F temperature=0.0
```

## Formato della risposta

### Senza timestamp

```json
{
  "text": "Transcribed text content",
  "processing_time": 2.34,
  "response_size_bytes": 1234,
  "duration_seconds": 10.5,
  "model": "whisper-large-v3"
}
```

### Con timestamp

```json
{
  "segments": [
    {
      "start_time_ms": 0,
      "end_time_ms": 5000,
      "text": "First segment of text"
    },
    {
      "start_time_ms": 5000,
      "end_time_ms": 10000,
      "text": "Second segment of text"
    }
  ],
  "text": "First segment of text Second segment of text",
  "processing_time": 3.45,
  "response_size_bytes": 2345,
  "duration_seconds": 10.5,
  "model": "whisper-large-v3"
}
```

## Uso avanzato

### Utilizzo con modelli diversi

Puoi usare qualsiasi modello Whisper modificando il `model_path` nella configurazione:

1. Scarica un modello da Hugging Face
2. Aggiorna il `model_path` in `config.json`
3. Riavvia il servizio

Il modello raccomandato per il riconoscimento vocale in russo è [whisper-large-v3-russian-ties-podlodka-v1.2](https://huggingface.co/Apel-sin/whisper-large-v3-russian-ties-podlodka-v1.2).

### Accelerazione hardware

Il servizio seleziona automaticamente il dispositivo di calcolo migliore disponibile:
- GPU CUDA (indice dispositivo configurato tramite `device_id` in `config.json`)
- Apple Silicon MPS (per Mac con chip M1/M2/M3)
- CPU (fallback)

Per le migliori prestazioni su GPU NVIDIA, Flash Attention 2 viene usato quando disponibile.

### Cronologia delle trascrizioni

Quando `enable_history` è impostato su `true`, i risultati delle trascrizioni vengono salvati in una cartella `history` organizzata per data. Ogni trascrizione viene salvata come file JSON con il formato:
```
history/
└── YYYY-MM-DD/
    └── timestamp_filename_xxxx.json
```

## Risoluzione dei problemi

### Problemi nell'elaborazione audio

Se riscontri errori nell'elaborazione audio:
- Assicurati che FFmpeg e SoX siano installati sul sistema
- Verifica che il file audio non sia corrotto
- Prova parametri diversi di pre-elaborazione audio nella configurazione

### Problemi di prestazioni

In caso di trascrizione lenta:
- Usa una GPU se disponibile
- Regola i parametri `chunk_length_s` e `batch_size`
- Considera l'uso di un modello Whisper più piccolo
- Riduci `audio_rate` se la qualità completa non è necessaria
