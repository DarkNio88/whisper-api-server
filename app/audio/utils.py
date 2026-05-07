"""
Funzioni utilitarie per l'elaborazione audio.
"""

import os
import subprocess
import wave
import numpy as np
from scipy.signal import resample_poly
import logging
from typing import Tuple

logger = logging.getLogger('app.audio_utils')


def load_audio(file_path: str, sr: int = 16000) -> Tuple[np.ndarray, int]:
    """
    Carica un file audio utilizzando la libreria wave.

    Args:
        file_path: Percorso del file audio.
        sr: Frequenza di campionamento target.

    Returns:
        Tupla (array numpy, frequenza di campionamento).
    """
    try:
        with wave.open(file_path, 'rb') as wav_file:
            if wav_file.getnchannels() != 1:
                logger.warning("Il file %s non è mono-audio", file_path)

            frames = wav_file.readframes(-1)
            audio_array = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            sampling_rate = wav_file.getframerate()

            if sampling_rate != sr:
                gcd = np.gcd(sr, sampling_rate)
                audio_array = resample_poly(audio_array, sr // gcd, sampling_rate // gcd)
                sampling_rate = sr

            return audio_array, sampling_rate

    except Exception as e:
        logger.error("Errore durante il caricamento dell'audio %s: %s", file_path, e)
        raise


def get_audio_duration(file_path: str) -> float:
    """
    Determina la durata del file audio usando ffprobe.

    Args:
        file_path: Percorso del file audio.

    Returns:
        Durata in secondi.
    """
    if not os.path.exists(file_path):
        raise Exception(f"File non esistente: {file_path}")

    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
        return float(result.stdout.strip())
    except subprocess.TimeoutExpired:
        raise Exception(f"Timeout nel determinare la durata del file {file_path}")
    except subprocess.CalledProcessError as e:
        raise Exception(f"Errore ffprobe per il file {file_path}: {e.stderr}")
    except (ValueError, TypeError) as e:
        raise Exception(f"Errore nella conversione della durata per il file {file_path}: {e}")
