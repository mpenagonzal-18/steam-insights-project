import kagglehub
import shutil
from pathlib import Path

def run():
    cache_path = Path(
        kagglehub.dataset_download(
            "antonkozyriev/game-recommendations-on-steam"
        )
    )
    # MOVEMOS EL DATASET DESDE LA CACHÉ AL DIRECTORIO NUEVO
    target_dir = Path(__file__).resolve().parent / "data" / "raw"
    target_dir.mkdir(parents = True, exist_ok = True)

    shutil.copytree(cache_path, target_dir, dirs_exist_ok=True)

    data_path = target_dir

    print("Dataset location:", data_path)
    return data_path

if __name__ == "__main__":
    run()
