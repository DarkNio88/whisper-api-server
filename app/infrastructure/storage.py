"""
Utilità per la gestione dei file temporanei.
"""

import os
import tempfile
import logging

logger = logging.getLogger('app.file_manager')


def create_temp_file(suffix: str = ".wav") -> str:
    """
    Crea un file temporaneo con un nome univoco.

    Args:
        suffix: Estensione del file temporaneo.

    Returns:
        Percorso del file temporaneo.
    """
    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    logger.debug("File temporaneo creato: %s", temp_path)
    return temp_path


def cleanup_temp_files(file_paths: list) -> None:
    """
    Rimuove i file temporanei.

    Args:
        file_paths: Lista dei percorsi dei file da eliminare.
    """
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.debug("File temporaneo rimosso: %s", path)
        except Exception as e:
            logger.warning("Impossibile rimuovere il file temporaneo %s: %s", path, e)
