"""
Modulo async_tasks.py contiene funzioni per l'elaborazione asincrona delle attività.
"""

import copy
import uuid
import time
from typing import Dict, Any, Callable, Optional
from threading import Thread, Lock
import logging

logger = logging.getLogger('app.async_tasks')


class AsyncTaskManager:
    """
    Manager delle attività asincrone basato sui thread.

    Attributes:
        tasks (Dict): Dizionario per memorizzare le informazioni sulle attività.
    """
    
    TASK_TTL = 3600  # 1 ora

    def __init__(self):
        """
        Inizializzazione del manager delle attività asincrone.
        """
        self._lock = Lock()
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self._start_cleanup_thread()
    
    def run_task(self, func: Callable, *args, **kwargs) -> str:
        """
        Avvia un'attività in un thread separato.

        Args:
            func: Funzione da eseguire.
            *args: Argomenti posizionali per la funzione.
            **kwargs: Argomenti nominativi per la funzione.

        Returns:
            ID dell'attività.
        """
        task_id = str(uuid.uuid4())

        with self._lock:
            self._cleanup_old_tasks()
            self.tasks[task_id] = {
                "status": "pending",
                "result": None,
                "error": None,
                "created_at": time.time(),
                "started_at": None,
                "completed_at": None
            }

        thread = Thread(target=self._run_task_thread, args=(task_id, func, args, kwargs))
        thread.daemon = True
        thread.start()

        return task_id

    def _cleanup_old_tasks(self) -> None:
        """Elimina le attività concluse più vecchie di TASK_TTL. Deve essere chiamato sotto self._lock."""
        now = time.time()
        expired = [
            tid for tid, info in self.tasks.items()
            if info["completed_at"] and now - info["completed_at"] > self.TASK_TTL
        ]
        for tid in expired:
            del self.tasks[tid]
    
    def _run_task_thread(self, task_id: str, func: Callable, args: tuple, kwargs: dict) -> None:
        """
        Funzione per l'esecuzione dell'attività nel thread.

        Args:
            task_id: ID dell'attività.
            func: Funzione da eseguire.
            args: Argomenti posizionali per la funzione.
            kwargs: Argomenti nominativi per la funzione.
        """
        with self._lock:
            self.tasks[task_id]["status"] = "running"
            self.tasks[task_id]["started_at"] = time.time()

        try:
            result = func(*args, **kwargs)

            with self._lock:
                self.tasks[task_id]["status"] = "completed"
                self.tasks[task_id]["result"] = result
                self.tasks[task_id]["completed_at"] = time.time()

            logger.info("Attività %s completata con successo", task_id)
        except Exception as e:
            with self._lock:
                self.tasks[task_id]["status"] = "failed"
                self.tasks[task_id]["error"] = str(e)
                self.tasks[task_id]["completed_at"] = time.time()

            logger.error("Attività %s terminata con errore: %s", task_id, e)
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Recupera lo stato dell'attività.

        Args:
            task_id: ID dell'attività.

        Returns:
            Informazioni sull'attività o None se non trovata.
        """
        with self._lock:
            task = self.tasks.get(task_id)
            return copy.deepcopy(task) if task else None

    def _start_cleanup_thread(self) -> None:
        """Avvia un thread in background per la pulizia periodica delle attività vecchie."""
        def _cleanup_loop():
            while True:
                time.sleep(600)  # Ogni 10 minuti
                with self._lock:
                    self._cleanup_old_tasks()

        thread = Thread(target=_cleanup_loop, daemon=True)
        thread.start()


# Istanza globale del manager delle attività asincrone
task_manager = AsyncTaskManager()


def transcribe_audio_async(file_path: str, transcription_service, params: Dict = None) -> str:
    """
    Trascrizione asincrona di un file audio.

    Args:
        file_path: Percorso del file audio.
        transcription_service: Istanza di TranscriptionService.
        params: Parametri per la trascrizione.

    Returns:
        ID dell'attività.
    """
    params = params or {}
    def _transcribe():
        return transcription_service.transcribe(file_path, "async_task", params)
    return task_manager.run_task(_transcribe)