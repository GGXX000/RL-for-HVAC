#!/usr/bin/env python3
"""
为 7 月联合仿真实验准备建筑 IDF 与都灵 EPW 气象文件。

脚本会下载 DOE Commercial Reference Building 的 Small Office 包，提取最接近
Simple Office 案例的 IDF，并下载意大利都灵 EPW 气象文件。同时生成机器可读的
manifest，供后续仿真脚本统一读取路径。

脚本仅使用 Python 标准库，因此可以在研究环境的其他依赖安装之前运行。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


DOE_SMALL_OFFICE_PAGE = (
    "https://www.energy.gov/eere/articles/reference-buildings-building-type-small-office"
)

DOE_SMALL_OFFICE_KEYWORDS = (
    "smalloffice",
    "small_office",
    "small office",
)

TURIN_EPW_CANDIDATES = (
    # Climate.OneBuilding 当前将 Turin-Caselle 放在 Italy / Piedmont 目录下。
    "https://climate.onebuilding.org/WMO_Region_6_Europe/ITA_Italy/PM_Piedmont/"
    "ITA_PM_Torino-Caselle.AP.160590_TMYx.zip",
    "https://climate.onebuilding.org/WMO_Region_6_Europe/ITA_Italy/PM_Piedmont/"
    "ITA_PM_Torino-Caselle.AP.160590_TMYx.2011-2025.zip",
    "https://climate.onebuilding.org/WMO_Region_6_Europe/ITA_Italy/PM_Piedmont/"
    "ITA_PM_Torino-Caselle.AP.160590_TMYx.2009-2023.zip",
    # EnergyPlus 官方天气下载入口的集合后缀历史上发生过变化，因此保留两个常见候选。
    "https://energyplus.net/weather-download/europe_wmo_region_6/ITA/"
    "ITA_Torino-Caselle.160590_IGDG/ITA_Torino-Caselle.160590_IGDG.epw",
    "https://energyplus.net/weather-download/europe_wmo_region_6/ITA/"
    "ITA_Torino-Caselle.160590_IWEC/ITA_Torino-Caselle.160590_IWEC.epw",
    # OneBuilding 镜像了较新的 TMYx 天气文件，可作为 EnergyPlus 集合变化时的回退。
    "https://climate.onebuilding.org/WMO_Region_6_Europe/ITA_Italy/PM_Piedmont/"
    "ITA_PM_Torino-Caselle.AP.160590_TMYx.2004-2018.zip",
)

EXPECTED_BUILDING = {
    "name": "DOE Small Office / Simple Office",
    "thermal_zones": 5,
    "conditioned_floor_area_m2": 511,
    "volume_m3": 1559,
    "u_values_w_m2_k": {
        "wall": 0.78,
        "roof": 0.20,
        "ground_floor": 1.85,
        "window": 3.24,
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; building-drl-reproduction/1.0; "
        "+https://energyplus.net)"
    )
}


@dataclass(frozen=True)
class DownloadResult:
    url: str
    path: Path
    sha256: str
    bytes: int


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.links.append(value)


def request_url(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_file(urls: Iterable[str], destination: Path, force: bool = False) -> DownloadResult:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force:
        return DownloadResult(
            url="existing-file",
            path=destination,
            sha256=sha256_file(destination),
            bytes=destination.stat().st_size,
        )

    errors: list[str] = []
    for url in urls:
        try:
            print(f"正在下载 {url}")
            data = request_url(url)
            destination.write_bytes(data)
            return DownloadResult(
                url=url,
                path=destination,
                sha256=sha256_file(destination),
                bytes=destination.stat().st_size,
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            errors.append(f"{url}: {exc}")
            time.sleep(0.5)

    joined = "\n  - ".join(errors)
    raise RuntimeError(f"无法下载 {destination.name}。已尝试：\n  - {joined}")


def discover_doe_small_office_urls() -> list[str]:
    candidates: list[str] = []
    try:
        html = request_url(DOE_SMALL_OFFICE_PAGE).decode("utf-8", errors="replace")
        parser = LinkParser()
        parser.feed(html)
        for link in parser.links:
            decoded = urllib.parse.unquote(link).lower()
            if not decoded.endswith(".zip"):
                continue
            if any(keyword in decoded for keyword in DOE_SMALL_OFFICE_KEYWORDS):
                candidates.append(urllib.parse.urljoin(DOE_SMALL_OFFICE_PAGE, link))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"无法从 DOE 页面发现下载链接，将使用回退地址。原因：{exc}")

    # 旧版 DOE 页面曾在 /sites/default/files 或 /sites/prod/files 下使用可预测文件名。
    # 在页面发现链接之后保留这些可能的回退地址。
    fallbacks = [
        "https://www.energy.gov/sites/default/files/2013/12/f5/"
        "refbldg_smalloffice_new2004_v1-4_7-2.zip",
        "https://www.energy.gov/sites/default/files/2013/12/f5/"
        "refbldg_smalloffice_new2004_v1.3_5.0.zip",
        "https://www.energy.gov/sites/default/files/2014/02/f8/"
        "refbldg_smalloffice_new2004_v1-4_7-2.zip",
        "https://www.energy.gov/sites/prod/files/2014/02/f8/"
        "refbldg_smalloffice_new2004_v1-4_7-2.zip",
        "https://www.energy.gov/sites/default/files/2014/02/f8/"
        "refbldg_smalloffice_v1-4_7-2.zip",
        "https://www.energy.gov/sites/prod/files/2014/02/f8/"
        "refbldg_smalloffice_v1-4_7-2.zip",
    ]
    return list(dict.fromkeys(candidates + fallbacks))


def unzip_archive(zip_path: Path, extract_dir: Path, force: bool = False) -> None:
    if extract_dir.exists() and force:
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    marker = extract_dir / ".extracted"
    if marker.exists() and not force:
        return
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(extract_dir)
    marker.write_text(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), encoding="utf-8")


def select_small_office_idf(extract_dir: Path, climate_zone: str) -> Path:
    idfs = sorted(extract_dir.rglob("*.idf"))
    if not idfs:
        raise FileNotFoundError(f"在 {extract_dir} 下未找到 IDF 文件")

    scored: list[tuple[int, Path]] = []
    for idf in idfs:
        name = idf.name.lower()
        score = 0
        climate_token = f"_{climate_zone.lower()}_"
        if climate_token in name:
            score += 50
        if "smalloffice" in name or "small_office" in name:
            score += 20
        if "new2004" in name:
            score += 10
        if "new" in name:
            score += 5
        if "usa" in name:
            score += 1
        scored.append((score, idf))

    scored.sort(key=lambda item: (item[0], -len(str(item[1]))), reverse=True)
    return scored[0][1]


def extract_epw_if_zip(weather_download: Path, output_epw: Path) -> Path:
    if not zipfile.is_zipfile(weather_download):
        if weather_download != output_epw:
            shutil.copy2(weather_download, output_epw)
        return output_epw

    with zipfile.ZipFile(weather_download) as archive:
        epw_names = [name for name in archive.namelist() if name.lower().endswith(".epw")]
        if not epw_names:
            raise FileNotFoundError(f"{weather_download} 内未找到 EPW 文件")
        chosen = sorted(epw_names, key=lambda value: ("torino" not in value.lower(), len(value)))[0]
        output_epw.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(chosen) as src, output_epw.open("wb") as dst:
            shutil.copyfileobj(src, dst)
    return output_epw


def parse_epw_location(epw_path: Path) -> dict[str, str | float]:
    first_line = epw_path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    fields = next(csv.reader([first_line]))
    if len(fields) < 10 or fields[0].upper() != "LOCATION":
        raise ValueError(f"{epw_path} 看起来不是 EPW 文件")
    return {
        "city": fields[1],
        "state_province": fields[2],
        "country": fields[3],
        "source": fields[4],
        "wmo": fields[5],
        "latitude": float(fields[6]),
        "longitude": float(fields[7]),
        "time_zone": float(fields[8]),
        "elevation_m": float(fields[9]),
    }


def write_july_weather_csv(epw_path: Path, output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with epw_path.open("r", encoding="utf-8", errors="replace", newline="") as src:
        reader = csv.reader(src)
        for _ in range(8):
            next(reader)
        with output_csv.open("w", encoding="utf-8", newline="") as dst:
            writer = csv.writer(dst)
            writer.writerow(
                [
                    "month",
                    "day",
                    "hour",
                    "minute",
                    "dry_bulb_c",
                    "relative_humidity_pct",
                    "global_horizontal_radiation_wh_m2",
                    "direct_normal_radiation_wh_m2",
                    "diffuse_horizontal_radiation_wh_m2",
                    "wind_speed_m_s",
                ]
            )
            for row in reader:
                if not row or int(row[1]) != 7:
                    continue
                writer.writerow([row[1], row[2], row[3], row[4], row[6], row[8], row[13], row[14], row[15], row[21]])


def maybe_convert_idf(idf_path: Path, target_dir: Path, energyplus_bin: str | None) -> Path:
    if not energyplus_bin:
        return idf_path
    if not shutil.which(energyplus_bin) and not Path(energyplus_bin).exists():
        raise FileNotFoundError(f"未找到 EnergyPlus 可执行文件：{energyplus_bin}")

    target = target_dir / "small_office_energyplus_9_6.idf"
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(idf_path, target)
    print(
        "EnergyPlus IDF 版本转换依赖本机安装。"
        f"已将源 IDF 复制到 {target}；如果源版本不同，请运行 EnergyPlus 官方 "
        "transition 工具转换到 9.6.0。"
    )
    return target


def write_manifest(manifest_path: Path, payload: dict) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def manifest_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()).as_posix())
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="项目根目录。")
    parser.add_argument("--force", action="store_true", help="重新下载并重新解压数据。")
    parser.add_argument(
        "--energyplus-bin",
        default=os.environ.get("ENERGYPLUS_BIN"),
        help="可选的 EnergyPlus 9.6 可执行文件路径，用于后续 IDF 转换检查。",
    )
    parser.add_argument(
        "--climate-zone",
        default="4A",
        help=(
            "优先选择的 DOE Reference Building 气候区 IDF。"
            "默认 4A，作为意大利北部气候的保守代理。"
        ),
    )
    args = parser.parse_args()

    root = args.root.resolve()
    raw_dir = root / "data" / "raw"
    interim_dir = root / "data" / "interim"
    processed_dir = root / "data" / "processed"

    small_office_urls = discover_doe_small_office_urls()
    building_zip = raw_dir / "doe_small_office_reference_building.zip"
    building_result = download_file(small_office_urls, building_zip, force=args.force)

    building_extract_dir = interim_dir / "doe_small_office_reference_building"
    unzip_archive(building_zip, building_extract_dir, force=args.force)
    source_idf = select_small_office_idf(building_extract_dir, args.climate_zone)
    prepared_idf = maybe_convert_idf(source_idf, processed_dir, args.energyplus_bin)

    weather_download = raw_dir / "turin_weather_download.bin"
    weather_result = download_file(TURIN_EPW_CANDIDATES, weather_download, force=args.force)
    epw_path = extract_epw_if_zip(weather_download, processed_dir / "turin_italy.epw")
    july_csv_path = processed_dir / "turin_italy_july_weather.csv"
    write_july_weather_csv(epw_path, july_csv_path)

    epw_location = parse_epw_location(epw_path)
    manifest = {
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "expected_building": EXPECTED_BUILDING,
        "building_download": {
            "url": building_result.url,
            "path": manifest_path(building_result.path, root),
            "sha256": building_result.sha256,
            "bytes": building_result.bytes,
        },
        "weather_download": {
            "url": weather_result.url,
            "path": manifest_path(weather_result.path, root),
            "sha256": weather_result.sha256,
            "bytes": weather_result.bytes,
        },
        "source_idf": manifest_path(source_idf, root),
        "prepared_idf": manifest_path(prepared_idf, root),
        "epw": manifest_path(epw_path, root),
        "july_weather_csv": manifest_path(july_csv_path, root),
        "epw_location": epw_location,
        "simulation_period": {
            "start_month": 7,
            "start_day": 1,
            "end_month": 7,
            "end_day": 31,
            "timestep_minutes": 30,
        },
    }
    write_manifest(processed_dir / "asset_manifest.json", manifest)

    print("\n已准备的数据资产：")
    print(f"  IDF: {prepared_idf}")
    print(f"  EPW: {epw_path}")
    print(f"  July CSV: {july_csv_path}")
    print(f"  Manifest: {processed_dir / 'asset_manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
