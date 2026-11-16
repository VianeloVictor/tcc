"""Executa no Wokwi as 27 combinacoes e grava um log CSV compativel com Excel.

Execute na raiz do projeto: python .\\scripts\\rodar_testes_wokwi.py
Requer PlatformIO, Wokwi CLI e WOKWI_CLI_TOKEN configurado no ambiente.
"""

import csv
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from itertools import product
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "LOG_testes_wokwi.csv"
SERIAL_DIR = ROOT / "LOG_testes_wokwi_serial"
TIMEOUT_MS = 45000
DAYS_PER_WEEK = 7
ADC_MAX = 4095

TEMPERATURES = (("baixa", 80.0), ("normal", 98.0), ("alta", 115.0))
PRESSURES = (("baixa", 0.2), ("normal", 0.8), ("alta", 1.5))
VOLTAGES = (("baixa", 12.0), ("normal", 14.0), ("alta", 15.0))

FIELDS = (
    "Cenario",
    "Data/hora UTC",
    "Status da execucao Wokwi",
    "Faixa temperatura",
    "Temperatura configurada (C)",
    "Posicao potenciometro temperatura (0-1)",
    "ADC esperado temperatura (0-4095)",
    "Faixa pressao",
    "Pressao configurada (bar)",
    "Posicao potenciometro pressao (0-1)",
    "ADC esperado pressao (0-4095)",
    "Faixa tensao",
    "Tensao configurada (V)",
    "Posicao potenciometro tensao (0-1)",
    "ADC esperado tensao (0-4095)",
    "Dias por semana",
    "Status esperado temperatura",
    "Status esperado pressao",
    "Status esperado tensao",
    "Diagnostico geral esperado",
    "Media temperatura medida (C)",
    "Minima temperatura medida (C)",
    "Maxima temperatura medida (C)",
    "Status temperatura medido",
    "Media pressao medida (bar)",
    "Minima pressao medida (bar)",
    "Maxima pressao medida (bar)",
    "Status pressao medido",
    "Media tensao medida (V)",
    "Minima tensao medida (V)",
    "Maxima tensao medida (V)",
    "Status tensao medido",
    "Diagnostico geral medido",
    "Resultado",
    "Codigo de saida Wokwi CLI",
    "Arquivo serial",
    "Observacoes",
)


def classify_temperature(value):
    return "OK" if 90.0 <= value <= 105.0 else "CUIDADO"


def classify_pressure(value):
    if value < 0.3:
        return "CUIDADO"
    return "OK" if abs(value - 0.8) <= 0.3 else "CUIDADO"


def classify_voltage(value):
    return "OK" if 13.5 <= value <= 14.5 else "CUIDADO"


def adc_and_position(minimum, maximum, value):
    adc = round((value - minimum) / (maximum - minimum) * ADC_MAX)
    return adc, adc / ADC_MAX


def make_cases():
    cases = []
    for number, (temperature, pressure, voltage) in enumerate(
        product(TEMPERATURES, PRESSURES, VOLTAGES), start=1
    ):
        temp_adc, temp_position = adc_and_position(40.0, 140.0, temperature[1])
        pressure_adc, pressure_position = adc_and_position(0.0, 8.0, pressure[1])
        voltage_adc, voltage_position = adc_and_position(9.0, 16.0, voltage[1])
        statuses = (
            classify_temperature(temperature[1]),
            classify_pressure(pressure[1]),
            classify_voltage(voltage[1]),
        )
        cases.append(
            {
                "number": number,
                "temperature": temperature,
                "pressure": pressure,
                "voltage": voltage,
                "adc": (temp_adc, pressure_adc, voltage_adc),
                "positions": (temp_position, pressure_position, voltage_position),
                "expected": statuses,
                "general": "OK" if all(status == "OK" for status in statuses) else "CUIDADO",
            }
        )

    temperature = ("normal", 98.0)
    pressure = ("baixa", 0.2)
    voltage = ("normal", 14.0)
    daily_readings = (
        (98.0, 0.20, 13.60),
        (99.0, 0.21, 13.70),
        (100.0, 0.22, 13.80),
        (101.0, 0.23, 14.00),
        (102.0, 0.24, 14.10),
        (103.0, 0.25, 14.30),
        (106.0, 0.45, 14.40),
    )
    temperature = ("variavel", sum(reading[0] for reading in daily_readings) / 7)
    pressure = ("variavel", sum(reading[1] for reading in daily_readings) / 7)
    voltage = ("variavel", sum(reading[2] for reading in daily_readings) / 7)
    temp_adc, temp_position = adc_and_position(40.0, 140.0, temperature[1])
    pressure_adc, pressure_position = adc_and_position(0.0, 8.0, pressure[1])
    voltage_adc, voltage_position = adc_and_position(9.0, 16.0, voltage[1])
    statuses = (
        classify_temperature(temperature[1]),
        classify_pressure(pressure[1]),
        classify_voltage(voltage[1]),
    )
    cases.append(
        {
            "number": 28,
            "temperature": temperature,
            "pressure": pressure,
            "voltage": voltage,
            "adc": (temp_adc, pressure_adc, voltage_adc),
            "positions": (temp_position, pressure_position, voltage_position),
            "expected": statuses,
            "general": "OK" if all(status == "OK" for status in statuses) else "CUIDADO",
            "daily_readings": daily_readings,
        }
    )
    return cases


def format_number(value, digits=2):
    if value is None or value == "":
        return ""
    return f"{value:.{digits}f}".replace(".", ",")


def initial_row(case, status="NAO EXECUTADO", notes=""):
    temp, pressure, voltage = case["temperature"], case["pressure"], case["voltage"]
    temp_position, pressure_position, voltage_position = case["positions"]
    temp_adc, pressure_adc, voltage_adc = case["adc"]
    expected_temp, expected_pressure, expected_voltage = case["expected"]
    return {
        "Cenario": f"{case['number']:02}",
        "Data/hora UTC": "",
        "Status da execucao Wokwi": status,
        "Faixa temperatura": temp[0],
        "Temperatura configurada (C)": format_number(temp[1], 1),
        "Posicao potenciometro temperatura (0-1)": format_number(temp_position, 4),
        "ADC esperado temperatura (0-4095)": temp_adc,
        "Faixa pressao": pressure[0],
        "Pressao configurada (bar)": format_number(pressure[1], 2),
        "Posicao potenciometro pressao (0-1)": format_number(pressure_position, 4),
        "ADC esperado pressao (0-4095)": pressure_adc,
        "Faixa tensao": voltage[0],
        "Tensao configurada (V)": format_number(voltage[1], 2),
        "Posicao potenciometro tensao (0-1)": format_number(voltage_position, 4),
        "ADC esperado tensao (0-4095)": voltage_adc,
        "Dias por semana": DAYS_PER_WEEK,
        "Status esperado temperatura": expected_temp,
        "Status esperado pressao": expected_pressure,
        "Status esperado tensao": expected_voltage,
        "Diagnostico geral esperado": case["general"],
        "Resultado": status,
        "Observacoes": notes
        or (
            "Cenario complementar: sete leituras diferentes por dia; "
            "a temperatura de 106,0 C no dia 7 supera a media semanal "
            "e exercita a ramificacao de classificacao do sistema."
            if case["number"] == 28
            else ""
        ),
    }


def write_csv(rows):
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as log_file:
        writer = csv.DictWriter(
            log_file,
            fieldnames=FIELDS,
            delimiter=";",
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def load_existing_rows():
    if not CSV_PATH.exists():
        return None
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as log_file:
        reader = csv.DictReader(log_file, delimiter=";")
        if reader.fieldnames != list(FIELDS):
            return None
        return {row["Cenario"]: row for row in reader}


def merged_rows(selected_rows, existing_rows):
    if not existing_rows:
        return selected_rows
    merged = dict(existing_rows)
    for row in selected_rows:
        merged[row["Cenario"]] = row
    return [merged[number] for number in sorted(merged, key=int)]


def find_executable(names, fallback_paths=()):
    for name in names:
        executable = shutil.which(name)
        if executable:
            return executable
    for path in fallback_paths:
        if path.is_file():
            return str(path)
    return None


def normalized_text(text):
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )


def parse_measurements(text):
    text = normalized_text(text)
    pattern = re.compile(
        r"Media:\s*([\d.]+)\s*°?\s*(?:C|bar|V)\s*\|\s*"
        r"Minima:\s*([\d.]+)\s*°?\s*(?:C|bar|V)\s*\|\s*"
        r"Maxima:\s*([\d.]+)\s*°?\s*(?:C|bar|V)\s*\|\s*"
        r"Status:\s*(OK|CUIDADO)"
    )
    matches = pattern.findall(text)
    general = re.search(r"DIAGNOSTICO GERAL DO SISTEMA:\s*(OK|CUIDADO)", text)
    if len(matches) < 3:
        return None, general.group(1) if general else None
    return matches[-3:], general.group(1) if general else None


def scenario_text(case):
    if case["number"] == 28:
        lines = [
            "name: 'Cenario 28 - leituras diarias diferentes'",
            "version: 1",
            "steps:",
        ]
        for day, (temperature, pressure, voltage) in enumerate(
            case["daily_readings"], start=1
        ):
            temp_adc, temp_position = adc_and_position(40.0, 140.0, temperature)
            pressure_adc, pressure_position = adc_and_position(0.0, 8.0, pressure)
            voltage_adc, voltage_position = adc_and_position(9.0, 16.0, voltage)
            del temp_adc, pressure_adc, voltage_adc
            for part_id, position in (
                ("pot_temp", temp_position),
                ("pot_pressao", pressure_position),
                ("pot_tensao", voltage_position),
            ):
                lines.extend(
                    [
                        "  - set-control:",
                        f"      part-id: {part_id}",
                        "      name: position",
                        f"      value: {position:.8f}",
                    ]
                )
            lines.append(
                "  - wait-serial: "
                f"'[Semana 1 | Dia {day}/7]'"
            )
        lines.extend(
            [
                "  - wait-serial: 'DIAGNOSTICO GERAL DO SISTEMA: "
                + case["general"]
                + "'",
            ]
        )
        return "\n".join(lines) + "\n"

    positions = case["positions"]
    steps = [
        ("pot_temp", positions[0]),
        ("pot_pressao", positions[1]),
        ("pot_tensao", positions[2]),
    ]
    lines = [
        f"name: 'Cenario {case['number']:02}'",
        "version: 1",
        "steps:",
    ]
    for part_id, position in steps:
        lines.extend(
            [
                "  - set-control:",
                f"      part-id: {part_id}",
                "      name: position",
                f"      value: {position:.8f}",
            ]
        )
    lines.extend(
        [
            "  - wait-serial: 'DIAGNOSTICO GERAL DO SISTEMA: "
            + case["general"]
            + "'",
        ]
    )
    return "\n".join(lines) + "\n"


def update_observed(row, measurements, general):
    names = ("temperatura", "pressao", "tensao")
    units_digits = (1, 2, 2)
    statuses = []
    for name, digits, match in zip(names, units_digits, measurements):
        average, minimum, maximum, status = match
        row[f"Media {name} medida ({'C' if name == 'temperatura' else 'bar' if name == 'pressao' else 'V'})"] = (
            format_number(float(average), digits)
        )
        row[f"Minima {name} medida ({'C' if name == 'temperatura' else 'bar' if name == 'pressao' else 'V'})"] = (
            format_number(float(minimum), digits)
        )
        row[f"Maxima {name} medida ({'C' if name == 'temperatura' else 'bar' if name == 'pressao' else 'V'})"] = (
            format_number(float(maximum), digits)
        )
        row[f"Status {name} medido"] = status
        statuses.append(status)
    row["Diagnostico geral medido"] = general or ""
    return statuses


def main():
    parser = argparse.ArgumentParser(
        description="Executa os cenarios Wokwi e atualiza a planilha CSV."
    )
    parser.add_argument(
        "--cenario",
        type=int,
        choices=range(1, 29),
        metavar="1-28",
        help="executa somente o cenario informado",
    )
    arguments = parser.parse_args()

    cases = make_cases()
    if arguments.cenario:
        cases = [case for case in cases if case["number"] == arguments.cenario]
    rows = [initial_row(case) for case in cases]
    existing_rows = load_existing_rows() if arguments.cenario else None
    cli = find_executable(
        ("wokwi-cli", "wokwi-cli.exe"),
        (Path.home() / ".wokwi" / "bin" / "wokwi-cli.exe",),
    )
    pio = find_executable(
        ("pio", "platformio"),
        (
            Path.home() / ".platformio" / "penv" / "Scripts" / "platformio.exe",
            Path.home() / ".platformio" / "penv" / "Scripts" / "pio.exe",
        ),
    )
    blockers = []
    if not cli:
        blockers.append("Wokwi CLI nao encontrado; instale-o pelo guia oficial.")
    if not os.environ.get("WOKWI_CLI_TOKEN"):
        blockers.append("WOKWI_CLI_TOKEN nao configurado no ambiente.")
    if not pio:
        blockers.append("PlatformIO CLI nao encontrado.")
    if blockers:
        reason = " ".join(blockers)
        for row in rows:
            row["Observacoes"] = reason
        write_csv(merged_rows(rows, existing_rows) if arguments.cenario else rows)
        print(reason, file=sys.stderr)
        print(f"Planilha criada com {len(cases)} casos pendentes: {CSV_PATH}")
        return 2

    build = subprocess.run(
        [pio, "run", "-e", "esp32dev"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if build.returncode:
        reason = "Falha ao compilar firmware: " + build.stderr[-1000:].strip()
        for row in rows:
            row["Observacoes"] = reason
        write_csv(merged_rows(rows, existing_rows) if arguments.cenario else rows)
        print(build.stdout, file=sys.stderr)
        print(build.stderr, file=sys.stderr)
        return build.returncode

    SERIAL_DIR.mkdir(exist_ok=True)
    completed = 0

    with tempfile.TemporaryDirectory(prefix=".wokwi-cenarios-", dir=ROOT) as temp_dir:
        temp_path = Path(temp_dir)
        for index, case in enumerate(cases):
            row = initial_row(case)
            row["Data/hora UTC"] = datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            )
            scenario_path = temp_path / f"cenario_{case['number']:02}.yaml"
            scenario_path.write_text(scenario_text(case), encoding="utf-8")
            serial_path = SERIAL_DIR / f"cenario_{case['number']:02}.txt"
            attempt_serial_path = temp_path / f"serial_{case['number']:02}.txt"
            scenario_relative = scenario_path.relative_to(ROOT).as_posix()
            serial_relative = serial_path.relative_to(ROOT).as_posix()
            attempt_serial_relative = attempt_serial_path.relative_to(ROOT).as_posix()
            command = [
                cli,
                ".",
                "--scenario",
                scenario_relative,
                "--timeout",
                str(TIMEOUT_MS),
                "--serial-log-file",
                attempt_serial_relative,
                "--expect-text",
                f"DIAGNOSTICO GERAL DO SISTEMA: {case['general']}",
            ]
            result = subprocess.run(
                command,
                cwd=ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
            )
            serial_text = ""
            if attempt_serial_path.exists():
                shutil.copyfile(attempt_serial_path, serial_path)
                serial_text = attempt_serial_path.read_text(
                    encoding="utf-8", errors="replace"
                )
            output = serial_text or result.stdout + "\n" + result.stderr
            measurements, general = parse_measurements(output)
            row["Status da execucao Wokwi"] = "EXECUTADO"
            row["Codigo de saida Wokwi CLI"] = result.returncode
            row["Arquivo serial"] = serial_relative if serial_path.exists() else ""
            row["Observacoes"] = (result.stderr or result.stdout).strip()[-1000:]

            if measurements:
                observed_statuses = update_observed(row, measurements, general)
                expected = case["expected"]
                passed = tuple(observed_statuses) == expected and general == case["general"]
                row["Resultado"] = "PASSOU" if passed else "FALHOU"
            else:
                row["Resultado"] = "FALHOU"
                row["Observacoes"] = (
                    row["Observacoes"] or "Nao foi possivel ler o diagnostico completo do Serial."
                )

            rows[index] = row
            completed += 1
            write_csv(merged_rows(rows, existing_rows) if arguments.cenario else rows)
            print(
                f"Cenario {case['number']:02}/{len(cases)}: {row['Resultado']} "
                f"(codigo Wokwi CLI {result.returncode})"
            )

            if result.returncode and not measurements:
                reason = "Execucao interrompida: falha do Wokwi CLI sem diagnostico serial."
                for pending_row in rows[index + 1 :]:
                    pending_row["Observacoes"] = reason
                write_csv(merged_rows(rows, existing_rows) if arguments.cenario else rows)
                break

    passed_count = sum(row["Resultado"] == "PASSOU" for row in rows)
    print(
        f"\nTestes executados: {completed}; passaram: {passed_count}; "
        f"planilha: {CSV_PATH}"
    )
    print(f"Logs seriais: {SERIAL_DIR}")
    return 0 if completed == len(cases) and passed_count == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
