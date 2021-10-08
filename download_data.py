import os
import typing as t
import zipfile
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from itertools import repeat
from pathlib import Path
from threading import Event
from urllib.request import urlopen

import click
import npyscreen
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.spinner import Spinner
from rich.text import Text

done_event = Event()


download_progress = Progress(
    TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
    BarColumn(bar_width=None),
    "[progress.percentage]{task.percentage:>3.1f}%",
    "•",
    DownloadColumn(),
    "•",
    TransferSpeedColumn(),
    "•",
    TimeRemainingColumn(),
)


def get_spinner_with_name(name: str):
    return Spinner("pong", text=Text(name, style="green"))


def copy_url(task_id: TaskID, url: str, path: str) -> None:
    """Copy data from a url to a local file."""
    download_progress.console.log(f"Requesting {url}")
    response = urlopen(url)
    # This will break if the response doesn't contain content length
    try:
        # raise Exception
        download_progress.update(task_id, total=int(response.info()["Content-length"]))
    except KeyError:
        pass
    with open(path, "wb") as dest_file:
        download_progress.start_task(task_id)
        for data in iter(partial(response.read, 32768), b""):
            dest_file.write(data)
            download_progress.update(task_id, advance=len(data))
            if done_event.is_set():
                return
    download_progress.console.log(f"Downloaded {path}")


def download(
    urls: t.Iterable[str],
    file_names: t.Optional[t.Iterable[t.Optional[str]]],
    dest_dir: Path,
):
    """Download multiple files to the given directory."""

    if not file_names:
        file_names = repeat(None)

    with download_progress:
        with ThreadPoolExecutor(max_workers=4) as pool:
            for url, filename in zip(urls, file_names):
                if not filename:
                    filename = url.split("/")[-1]
                dest_path = dest_dir / filename
                if not dest_path.exists():
                    task_id = download_progress.add_task(
                        "download", filename=filename, start=False
                    )
                    pool.submit(copy_url, task_id, url, str(dest_path))
                else:
                    download_progress.console.log(
                        f"{filename} already exists! Download Skipped"
                    )


def download_i3d_breakfast(destination_path: Path):
    url = "https://zenodo.org/record/5179904/files/breakfast_i3d.zip?download=1"
    name = "i3d_breakfast"
    fn = f"{name}.zip"
    # step 1: download the large zip file
    download([url], [fn], destination_path)
    # FIXME: before going on, check the md5sum.
    # step 2: unzip the data
    if not (destination_path / name / "data").exists():
        download_progress.console.log(f"Extracting {fn}")
        with Live(
            Panel(get_spinner_with_name(fn), title="Extracting", border_style="blue"),
            refresh_per_second=20,
        ) as live:
            with zipfile.ZipFile(str(destination_path / fn), "r") as f:
                f.extractall(str(destination_path))
        download_progress.console.log(f"Extracted {fn}")
    else:
        download_progress.console.log(f"File {fn} was already extracted")


def download_hollywood_extend(destination_path: Path):
    raise NotImplementedError


all_datasets = {
    "Breakfast (I3D)": download_i3d_breakfast,
    "Hollywood Extended (I3D)": download_hollywood_extend,
}


class WhatToDownloadApp(npyscreen.NPSApp):
    # noinspection PyAttributeOutsideInit
    def main(self):
        self.form = npyscreen.Form(name="Select what to download")
        self.select_input = self.form.add(
            npyscreen.TitleMultiSelect,
            name="Pick all datasets to download",
            values=list(all_datasets.keys()),
        )
        self.form.edit()


@click.command()
@click.option(
    "--destination",
    default="~/work/fifa/data/",
    type=click.Path(dir_okay=True, file_okay=False, writable=True),
)
def main(destination: str):
    download_names = list(all_datasets.keys())
    download_functions: t.List[t.Callable[[Path], None]] = list(all_datasets.values())
    destination = Path(os.path.expanduser(destination))
    destination.mkdir(exist_ok=True, parents=True)
    app = WhatToDownloadApp()
    app.run()
    indices_of_downloads = app.select_input.value

    for download_indice in indices_of_downloads:
        # fixme change to rich for printing here.
        print(download_names[download_indice])
        download_functions[download_indice](destination)


if __name__ == "__main__":
    main()
