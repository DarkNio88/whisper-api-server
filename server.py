import argparse
from app import WhisperServiceAPI

def main():
    """
    Servizio API locale compatibile con OpenAI per il riconoscimento vocale usando il modello Whisper.
    """

    # Parsing degli argomenti della riga di comando
    parser = argparse.ArgumentParser(description="Servizio di riconoscimento vocale usando il modello Whisper")
    parser.add_argument("--config", help="Percorso al file di configurazione", default="config.json")
    
    args = parser.parse_args()
    
    # Avvio del servizio
    service = WhisperServiceAPI(args.config)
    service.run()


if __name__ == "__main__":
    main()
