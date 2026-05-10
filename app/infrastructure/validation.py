"""
Modulo validation.py contiene classi e funzioni per la validazione dei dati in ingresso.
"""

import os
import magic
from typing import Dict, List
import logging

# Otteniamo il logger dalla configurazione centralizzata
logger = logging.getLogger('app.validators')


class ValidationError(Exception):
    """Eccezione per errori di validazione."""
    pass


class FileValidator:
    """
    Classe per la validazione dei file.

    Controlla il tipo di file, la dimensione e altri parametri basati sulla configurazione.
    """
    
    def __init__(self, config: Dict):
        """
        Inizializzazione del validatore dei file.

        Args:
            config: Dizionario con i parametri di configurazione.
        """
        self.validation_config = config.get("file_validation", {})
        self.max_file_size_mb = self.validation_config.get("max_file_size_mb", 100)
        self.allowed_extensions = self.validation_config.get("allowed_extensions", 
                                                             [".wav", ".mp3", ".ogg", ".flac", ".m4a"])
        self.allowed_mime_types = self.validation_config.get("allowed_mime_types", 
                                                            ["audio/wav", "audio/mpeg", "audio/ogg", 
                                                             "audio/flac", "audio/mp4"])
    
    def _validate_file_extension(self, filename: str) -> None:
        """
        Valida l'estensione del file.

        Args:
            filename: Nome del file.

        Raises:
            ValidationError: Se l'estensione del file non è nella lista consentita.
        """
        if not any(filename.lower().endswith(ext.lower()) for ext in self.allowed_extensions):
            # Registrazione del tentativo di caricare un file con estensione non consentita
            file_extension = os.path.splitext(filename)[1]
            logger.warning("Tentativo di caricare un file con estensione non consentita '%s'. "
                          "Nome file: %s. Estensioni consentite: %s", file_extension, filename, ", ".join(self.allowed_extensions))
            
            raise ValidationError(f"Estensione del file non consentita. "
                                 f"Estensioni consentite: {', '.join(self.allowed_extensions)}")

    def _normalize_mime(self, mime_type: str) -> str:
        """
        Normalizza alcuni alias comuni di MIME-type restituiti da sistemi diversi.

        Esempio: `audio/x-wav` -> `audio/wav`.
        """
        if not mime_type:
            return mime_type
        base = mime_type.split(";")[0].strip().lower()
        aliases = {
            "audio/x-wav": "audio/wav",
            "audio/vnd.wave": "audio/wav",
            "audio/x-m4a": "audio/mp4",
        }
        return aliases.get(base, base)
    
    def validate_file_by_path(self, file_path: str, filename: str) -> bool:
        """
        Valida il file dato il percorso sul disco.

        Args:
            file_path: Percorso del file.
            filename: Nome del file (per verificare l'estensione).

        Returns:
            True se il file ha superato la validazione.

        Raises:
            ValidationError: Se il file non supera la validazione.
        """
        # Controllo dell'estensione
        self._validate_file_extension(filename)

        # Controllo della dimensione
        file_size = os.path.getsize(file_path)
        max_size_bytes = self.max_file_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            raise ValidationError(f"La dimensione del file ({file_size / (1024*1024):.2f} MB) "
                                 f"supera il massimo consentito ({self.max_file_size_mb} MB)")

        # Controllo del tipo MIME (normalizziamo alias comuni come audio/x-wav)
        try:
            mime_type = magic.from_file(file_path, mime=True)
            normalized = self._normalize_mime(mime_type)
            if normalized not in self.allowed_mime_types:
                raise ValidationError(f"Il MIME-type del file ({mime_type}) non è consentito. "
                                     f"MIME-type consentiti: {', '.join(self.allowed_mime_types)}")
        except ValidationError:
            raise
        except Exception as e:
            logger.warning("Impossibile determinare il MIME-type del file: %s", e)

        return True
