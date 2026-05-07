"""
Il modulo config.py contiene funzioni per la gestione della configurazione dell'applicazione.
"""

import json
import os
import logging
from typing import Dict

logger = logging.getLogger('app.config')


def load_config(config_path: str) -> Dict:
    """
    Carica la configurazione da un file JSON.
    
    Args:
        config_path: Percorso del file di configurazione.
        
    Returns:
        Dizionario con i parametri di configurazione.
        
    Raises:
        FileNotFoundError: Se il file di configurazione non viene trovato.
        json.JSONDecodeError: Se il file di configurazione contiene JSON non valido.
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        logger.info("Configurazione caricata con successo da %s", config_path)
        return config
    except FileNotFoundError as e:
        logger.error("File di configurazione non trovato: %s", e)
        raise
    except json.JSONDecodeError as e:
        logger.error("Errore durante il caricamento della configurazione: %s", e)
        raise