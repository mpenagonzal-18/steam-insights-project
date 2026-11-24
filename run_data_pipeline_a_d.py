"""Run the whole Steam data pipeline in order, from points A to D."""
from scripts.download_data import run as download
from scripts.create_database import run as create_database
from scripts.create_staging import run as create_staging
from scripts.analyze_data import run as analyze
from scripts.create_schema import run as create_schema
from scripts.insert_data import run as insert


def main():
    data_path = download()
    create_database()
    create_staging(data_path)
    analyze()
    create_schema()
    insert(data_path)
    print("\nPipeline completed successfully.")


if __name__ == "__main__":
    main()
