from dotenv import load_dotenv


def run() -> None:
    load_dotenv()  # lädt Variablen aus .env (falls vorhanden)
    print("Hello from your new professional project!")


if __name__ == "__main__":
    run()
