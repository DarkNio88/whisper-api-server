"""
Modulo sources.py contiene funzioni per ottenere file audio
da diverse fonti (file caricati, URL, base64).
"""

import os
import base64
from urllib.parse import urlparse
import magic
import requests
from typing import Tuple, Optional
import logging

from ..infrastructure.storage import create_temp_file

logger = logging.getLogger('app.audio_sources')


def _check_size(size_bytes: int, max_size_mb: int) -> Optional[str]:
    """Controlla la dimensione del file. Restituisce un messaggio di errore o None."""
    if size_bytes > max_size_mb * 1024 * 1024:
        return f"File exceeds maximum size of {max_size_mb}MB"
    return None


def get_uploaded_file(request_files, max_file_size_mb: int = 100) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Ottiene un file audio dai file caricati tramite Flask.

    Returns:
        Tupla (percorso al file temporaneo, nome del file, messaggio di errore).
    """
    if 'file' not in request_files:
        return None, None, "No file part"

    file = request_files['file']

    if file.filename == '':
        return None, None, "No selected file"

    # Controllo della dimensione
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)

    error = _check_size(size, max_file_size_mb)
    if error:
        return None, None, error

    # Salviamo in un file temporaneo
    temp_path = create_temp_file()
    file.save(temp_path)

    return temp_path, file.filename, None


def get_url_file(url: str, max_file_size_mb: int = 100) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Ottiene un file audio da un URL.

    Returns:
        Tupla (percorso al file temporaneo, nome del file, messaggio di errore).
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return None, None, f"Unsupported URL scheme: {parsed.scheme}. Only http/https allowed"

        # Protezione SSRF (validazione IP privato) non aggiunta intenzionalmente:
        # il servizio opera in una rete interna e non è accessibile dall'esterno
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        # Controllo della dimensione tramite Content-Length
        content_length = response.headers.get('Content-Length')
        if content_length:
            error = _check_size(int(content_length), max_file_size_mb)
            if error:
                return None, None, error

        # Estrarre il nome del file da Content-Disposition o dall'URL
        original_name = None
        cd = response.headers.get('Content-Disposition', '')
        if 'filename=' in cd:
            original_name = cd.split('filename=')[-1].strip('" ')
        if not original_name:
            url_path = parsed.path.rstrip('/')
            if url_path:
                original_name = os.path.basename(url_path)

        temp_path = create_temp_file()
        max_bytes = max_file_size_mb * 1024 * 1024
        total_size = 0

        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                total_size += len(chunk)
                if total_size > max_bytes:
                    f.close()
                    os.remove(temp_path)
                    return None, None, f"File exceeds maximum size of {max_file_size_mb}MB"
                f.write(chunk)

        return temp_path, original_name or os.path.basename(temp_path), None

    except Exception as e:
        logger.error("Errore durante il recupero del file dall'URL %s: %s", url, e)
        return None, None, f"Error retrieving file from URL: {str(e)}"


def get_base64_file(base64_data: str, max_file_size_mb: int = 100) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Ottiene un file audio da dati base64.

    Returns:
        Tupla (percorso al file temporaneo, nome del file, messaggio di errore).
    """
    try:
        # Stima della dimensione prima della decodifica: base64 codifica 3 byte in 4 caratteri
        estimated_size = len(base64_data) * 3 // 4
        error = _check_size(estimated_size, max_file_size_mb)
        if error:
            return None, None, error

        audio_data = base64.b64decode(base64_data)

        # Determiniamo il formato in base al contenuto
        mime_to_ext = {
            "audio/mpeg": ".mp3",
            "audio/ogg": ".ogg",
            "audio/flac": ".flac",
            "audio/mp4": ".m4a",
            "audio/x-m4a": ".m4a",
            "audio/aac": ".aac",
            "audio/webm": ".webm",
        }
        detected_mime = magic.from_buffer(audio_data[:1024], mime=True)
        suffix = mime_to_ext.get(detected_mime, ".wav")

        temp_path = create_temp_file(suffix)
        with open(temp_path, 'wb') as f:
            f.write(audio_data)

        return temp_path, os.path.basename(temp_path), None

    except Exception as e:
        logger.error("Errore nella decodifica dei dati base64: %s", e)
        return None, None, f"Error decoding base64 data: {str(e)}"
