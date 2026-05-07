"""
Il modulo routes.py contiene le classi per la registrazione delle route API
del servizio di riconoscimento vocale.
"""

from __future__ import annotations

import os
from typing import Dict, TYPE_CHECKING
import logging

from flask import Flask, request, jsonify

from .core.transcription_service import TranscriptionService
from .audio.sources import get_uploaded_file, get_url_file, get_base64_file
from .infrastructure.validation import ValidationError
from .infrastructure.storage import cleanup_temp_files
from .infrastructure.async_tasks import transcribe_audio_async, task_manager

if TYPE_CHECKING:
    from .core.transcriber import WhisperTranscriber
    from .infrastructure.validation import FileValidator

logger = logging.getLogger('app.routes')


class Routes:
    """Classe per la registrazione di tutti gli endpoint API."""

    def __init__(self, app: Flask, transcriber: WhisperTranscriber,
                 config: Dict, file_validator: FileValidator):
        self.app = app
        self.config = config
        self.transcription_service = TranscriptionService(transcriber, config)
        self.file_validator = file_validator
        self._max_size = self.config.get("file_validation", {}).get("max_file_size_mb", 100)
        self._register_routes()

    def _register_routes(self) -> None:
        @self.app.route('/', methods=['GET'])
        def index():
            """Root. Restituisce la pagina client HTML."""
            return self.app.send_static_file('index.html')

        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Endpoint per verificare lo stato del servizio."""
            return jsonify({"status": "ok", "version": "1.0.0"}), 200

        @self.app.route('/config', methods=['GET'])
        def get_config():
            """Endpoint per ottenere la configurazione del servizio.
            Restituisce la configurazione completa inclusa model_path — decisione
            consapevole: il servizio opera in rete interna."""
            return jsonify(self.config), 200

        @self.app.route('/v1/models', methods=['GET'])
        def list_models():
            """Endpoint per ottenere la lista dei modelli disponibili."""
            return jsonify({
                "data": [{
                    "id": os.path.basename(self.config["model_path"]),
                    "object": "model",
                    "owned_by": "openai",
                    "permissions": []
                }],
                "object": "list"
            }), 200

        @self.app.route('/v1/models/<model_id>', methods=['GET'])
        def retrieve_model(model_id):
            """Endpoint per ottenere informazioni su un modello specifico."""
            if model_id == os.path.basename(self.config["model_path"]):
                return jsonify({
                    "id": model_id,
                    "object": "model",
                    "owned_by": "openai",
                    "permissions": []
                }), 200
            return jsonify({
                "error": "Model not found",
                "details": f"Model '{model_id}' does not exist"
            }), 404

        @self.app.route('/v1/audio/transcriptions', methods=['POST'])
        def openai_transcribe_endpoint():
            """Endpoint per la trascrizione di un file audio (multipart form)."""
            temp_path, filename, error = get_uploaded_file(request.files, self._max_size)
            if error:
                return jsonify({"error": error}), 400

            try:
                self.file_validator.validate_file_by_path(temp_path, filename)
                response, status_code = self.transcription_service.transcribe(temp_path, filename, dict(request.form))
                return jsonify(response), status_code
            except ValidationError as e:
                logger.warning("Errore di validazione del file '%s': %s", filename, e)
                return jsonify({"error": str(e)}), 400
            finally:
                cleanup_temp_files([temp_path])

        @self.app.route('/v1/audio/transcriptions/url', methods=['POST'])
        def transcribe_from_url():
            """Endpoint per la trascrizione di un file audio da URL."""
            data = request.json

            if not data or "url" not in data:
                return jsonify({
                    "error": "No URL provided",
                    "details": "Please provide 'url' in the JSON request"
                }), 400

            url = data["url"]
            params = {k: v for k, v in data.items() if k != "url"}

            temp_path, filename, error = get_url_file(url, self._max_size)
            if error:
                return jsonify({"error": error}), 400

            try:
                self.file_validator.validate_file_by_path(temp_path, filename)
                response, status_code = self.transcription_service.transcribe(temp_path, filename, params)
                return jsonify(response), status_code
            except ValidationError as e:
                logger.warning("Errore di validazione del file '%s': %s", filename, e)
                return jsonify({"error": str(e)}), 400
            finally:
                cleanup_temp_files([temp_path])

        @self.app.route('/v1/audio/transcriptions/base64', methods=['POST'])
        def transcribe_from_base64():
            """Endpoint per la trascrizione di audio codificato in base64."""
            data = request.json

            if not data or "file" not in data:
                return jsonify({
                    "error": "No base64 file provided",
                    "details": "Please provide 'file' in the JSON request"
                }), 400

            base64_data = data["file"]
            params = {k: v for k, v in data.items() if k != "file"}

            temp_path, filename, error = get_base64_file(base64_data, self._max_size)
            if error:
                return jsonify({"error": error}), 400

            try:
                self.file_validator.validate_file_by_path(temp_path, filename)
                response, status_code = self.transcription_service.transcribe(temp_path, filename, params)
                return jsonify(response), status_code
            except ValidationError as e:
                logger.warning("Errore di validazione del file '%s': %s", filename, e)
                return jsonify({"error": str(e)}), 400
            finally:
                cleanup_temp_files([temp_path])

        @self.app.route('/v1/audio/transcriptions/async', methods=['POST'])
        def transcribe_async():
            """Endpoint per la trascrizione asincrona di un file audio."""
            temp_path, filename, error = get_uploaded_file(request.files, self._max_size)
            if error:
                return jsonify({"error": error}), 400

            try:
                self.file_validator.validate_file_by_path(temp_path, filename)
            except ValidationError as e:
                cleanup_temp_files([temp_path])
                return jsonify({"error": str(e)}), 400

            params = dict(request.form)
            # Non pulire temp_path qui — il task asincrono si occupa della pulizia
            task_id = transcribe_audio_async(temp_path, self.transcription_service, params)
            return jsonify({"task_id": task_id}), 202

        @self.app.route('/v1/tasks/<task_id>', methods=['GET'])
        def get_task_status(task_id):
            """Endpoint per ottenere lo stato del task asincrono."""
            task_info = task_manager.get_task_status(task_id)

            if not task_info:
                return jsonify({"error": "Task not found"}), 404

            response = {"task_id": task_id, "status": task_info["status"]}

            if task_info["status"] == "completed":
                response["result"] = task_info["result"]
            elif task_info["status"] == "failed":
                response["error"] = task_info["error"]

            return jsonify(response)
