"""
Modulo principale dell'applicazione, contenente la classe WhisperServiceAPI
per l'inizializzazione e l'avvio del servizio di riconoscimento vocale.
"""

__all__ = ['WhisperServiceAPI']

import os
import logging
from flask import Flask
from flask_cors import CORS
from typing import Dict
import waitress

from .core.transcriber import WhisperTranscriber
from .core.config import load_config
from .routes import Routes
from .infrastructure.validation import FileValidator
from .infrastructure.log import setup_logging, RequestLogger


class WhisperServiceAPI:
    """
    Classe per l'API del servizio di riconoscimento vocale.

    Attributes:
        config (Dict): Dizionario con i parametri di configurazione.
        port (int): Porta del servizio.
        transcriber (WhisperTranscriber): Istanza del transcriber.
        app (Flask): Applicazione Flask.
        file_validator (FileValidator): Validatore dei file.
    """

    def __init__(self, config_path: str):
        """
        Inizializzazione dell'API del servizio.

        Args:
            config_path: Percorso al file di configurazione.
        """
        # Caricamento della configurazione
        self.config = load_config(config_path)
        
        # Impostazione del livello di logging
        log_level = getattr(logging, self.config.get('log_level', 'INFO').upper())
        log_file = self.config.get('log_file')
        setup_logging(log_level=log_level, log_file=log_file)
        
        # Otteniamo il logger per questo modulo
        self.logger = logging.getLogger('app')
        self.logger.info("Inizializzazione WhisperServiceAPI")
        
        # Inizializzazione dell'app Flask
        self.app = Flask(__name__)
        CORS(self.app)
        self.port = self.config["service_port"]
        
        # Inizializzazione dei componenti
        self.transcriber = WhisperTranscriber(self.config)
        self.file_validator = FileValidator(self.config)
        
        # Configurazione del logging delle richieste
        request_logger_config = self.config.get('request_logging', {})
        request_logger = RequestLogger(self.app, request_logger_config)
        
        # Registrazione delle route
        routes = Routes(self.app, self.transcriber, self.config, self.file_validator)
        
        self.logger.info("WhisperServiceAPI inizializzato con successo")

    def run(self) -> None:
        """Avvia il servizio tramite Waitress."""
        self.logger.info("Avvio del servizio su 0.0.0.0:%s", self.port)
        waitress.serve(self.app, host='0.0.0.0', port=self.port)

    def create_app(self) -> Flask:
        """
        Creazione e configurazione dell'app Flask (per l'utilizzo con server WSGI).

        Returns:
            Applicazione Flask configurata.
        """
        return self.app