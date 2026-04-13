from app.services.ingest.csv_ingest import run_ingest


def main():
    rows = run_ingest()

    print("rows:", len(rows))

    # preview first record
    if rows:
        print(rows[0])


if __name__ == "__main__":
    main()