#!/bin/bash

# Nome dell'ambiente conda
CONDA_ENV_NAME="whisper-api"

# Flag di aggiornamento (default false)
UPDATE_ENV=false

# Controllo della presenza dell'argomento --update
if [[ "$1" == "--update" ]]; then
    UPDATE_ENV=true
fi

# Controllo presenza di conda
if ! command -v conda &> /dev/null; then
    echo "Conda non è installato. Per favore installa conda e riprova."
    exit 1
fi

# Flag che indica se è stato creato un nuovo ambiente
NEW_ENV_CREATED=false

# Creazione dell'ambiente conda se non esiste
if ! conda env list | grep -q "$CONDA_ENV_NAME"; then
    echo "Creazione ambiente conda: $CONDA_ENV_NAME"
    conda create -n "$CONDA_ENV_NAME" python=3.12 -y
    NEW_ENV_CREATED=true
else
    echo "L'ambiente conda '$CONDA_ENV_NAME' esiste già."
fi

# Ottenimento del percorso di conda
CONDA_PATH=$(which conda)

# Verifica che il percorso di conda sia stato trovato
if [ -z "$CONDA_PATH" ]; then
    echo "Impossibile trovare il percorso di conda. Assicurati che conda sia installato e aggiunto al PATH."
    exit 1
fi

# Attivazione dell'ambiente conda
echo "Attivazione ambiente conda: $CONDA_ENV_NAME"
source $(dirname "$CONDA_PATH")/../etc/profile.d/conda.sh
conda activate "$CONDA_ENV_NAME"

# Installazione delle dipendenze al primo avvio o con il flag --update
if [[ "$NEW_ENV_CREATED" == true || "$UPDATE_ENV" == true ]]; then
    # Installazione delle dipendenze da requirements.txt
    if [ -f "requirements.txt" ]; then
        echo "Installazione delle dipendenze da requirements.txt"
        if ! pip install --no-cache-dir -r requirements.txt; then
            echo "Errore durante l'installazione delle dipendenze."
            exit 1
        fi
    else
        echo "File requirements.txt non trovato. Assicurati che si trovi nella stessa directory dello script."
        exit 1
    fi
fi

# Avvio del server
echo "Avvio del server..."
python server.py --config config.json

echo "Server fermato."
