"""
Modulo history.py — salvataggio della cronologia delle trascrizioni in file JSON.
"""

import os
import json
import shutil
import datetime
import random
import string
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger('app.history')

# Directory radice della cronologia (relativa alla radice del progetto)
_history_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "history")


def save_history(result: Dict[str, Any], original_filename: str, config: Dict) -> Optional[str]:
    """
    Salva il risultato della trascrizione in un file di cronologia.

    Args:
        result: Risultato della trascrizione.
        original_filename: Nome originale del file audio.
        config: Configurazione (verifica di enable_history).

    Returns:
        Il percorso del file salvato o None.
    """
    if not config.get("enable_history", False):
        return None

    try:
        os.makedirs(_history_root, exist_ok=True)

        now = datetime.datetime.now(tz=datetime.timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        timestamp_ms = int(now.timestamp() * 1000)
        random_tag = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        base_filename = os.path.basename(original_filename)

        date_dir = os.path.join(_history_root, date_str)
        os.makedirs(date_dir, exist_ok=True)

        history_path = os.path.join(date_dir, f"{timestamp_ms}_{base_filename}_{random_tag}.json")

        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info("Risultato salvato nella cronologia: %s", history_path)
        _cleanup_old_history(config)
        return history_path

    except Exception as e:
        logger.error("Errore durante il salvataggio della cronologia: %s", e)
        return None


def _cleanup_old_history(config: Dict) -> None:
    """
    Elimina le directory della cronologia più vecchie di max_history_days giorni.

    Args:
        config: Configurazione (si verifica max_history_days).
    """
    max_days = config.get("max_history_days", 30)
    if max_days <= 0:
        return

    cutoff = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=max_days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    try:
        for entry in os.listdir(_history_root):
            entry_path = os.path.join(_history_root, entry)
            if not os.path.isdir(entry_path):
                continue
            # Le directory hanno formato YYYY-MM-DD
            if len(entry) == 10 and entry < cutoff_str:
                shutil.rmtree(entry_path, ignore_errors=True)
                logger.info("Rimossa vecchia directory della cronologia: %s", entry)
    except Exception as e:
        logger.warning("Errore durante la pulizia della vecchia cronologia: %s", e)
