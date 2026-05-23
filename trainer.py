#!/usr/bin/env python3
"""
Spanisch-Vokabeltrainer für dein Auswandern nach Spanien.
Bei falschen Antworten erstellt die KI eine Eselsbrücke und ein kurzes Beispiel.
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import unicodedata
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore[misc, assignment]

BASE_DIR = Path(__file__).resolve().parent
VOKABELN_DATEI = BASE_DIR / "vokabeln.json"
ENV_DATEI = BASE_DIR / ".env"


def konfiguriere_ausgabe() -> None:
    """UTF-8 auf Windows, damit Pfeile und Umlaute in der Konsole funktionieren."""
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass


def lade_env() -> None:
    """Lädt KEY=VALUE aus .env, falls vorhanden."""
    if not ENV_DATEI.exists():
        return
    for zeile in ENV_DATEI.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#") or "=" not in zeile:
            continue
        key, _, wert = zeile.partition("=")
        os.environ.setdefault(key.strip(), wert.strip().strip('"').strip("'"))


def normalisiere(text: str) -> str:
    text = text.strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"\s+", " ", text)
    return text


def lade_vokabeln() -> list[dict[str, str]]:
    if not VOKABELN_DATEI.exists():
        print(f"Fehler: {VOKABELN_DATEI} nicht gefunden.")
        sys.exit(1)
    with VOKABELN_DATEI.open(encoding="utf-8") as f:
        daten = json.load(f)
    if not daten:
        print("Die Vokabelliste ist leer.")
        sys.exit(1)
    return daten


def ist_richtig(erwartet: str, eingabe: str) -> bool:
    return normalisiere(erwartet) == normalisiere(eingabe)


def ki_hilfe(
    frage: str,
    richtige_antwort: str,
    deine_antwort: str,
    richtung: str,
) -> str | None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    if OpenAI is None:
        return None

    client = OpenAI(api_key=api_key)
    prompt = f"""Du bist ein geduldiger Spanischlehrer für jemanden, der nach Spanien auswandert.

Der Schüler übt Vokabeln ({richtung}).
Frage: {frage}
Richtige Antwort: {richtige_antwort}
Eingabe des Schülers: {deine_antwort}

Analysiere kurz, warum die Eingabe falsch oder verwirrend sein könnte (z. B. falscher Artikel, falsches Wort, Tippfehler, Deutsch statt Spanisch).

Gib dann:
1. Eine einprägsame Eselsbrücke auf Deutsch (1–2 Sätze).
2. Ein kurzes Beispiel auf Spanisch (1 Satz) mit der richtigen Vokabel – Alltag in Spanien (Wohnung, Behörde, Einkaufen …).
3. Optional: ein Merkhinweis zu Artikel/Geschlecht, falls relevant.

Antworte auf Deutsch, kompakt (max. 120 Wörter), freundlich und konkret."""

    try:
        antwort = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Du hilfst beim Spanischlernen mit klaren Eselsbrücken und kurzen Beispielsätzen.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=350,
            temperature=0.7,
        )
        return antwort.choices[0].message.content.strip()
    except Exception as exc:
        return f"(KI-Feedback nicht verfügbar: {exc})"


def waehle_richtung() -> str:
    print("\nWie möchtest du üben?")
    print("  1 = Deutsch -> Spanisch (empfohlen)")
    print("  2 = Spanisch -> Deutsch")
    while True:
        wahl = input("Auswahl [1]: ").strip() or "1"
        if wahl in ("1", "2"):
            return "de->es" if wahl == "1" else "es->de"
        print("Bitte 1 oder 2 eingeben.")


def frage_stellen(vokabel: dict[str, str], richtung: str) -> tuple[str, str]:
    if richtung == "de->es":
        return vokabel["deutsch"], vokabel["spanisch"]
    return vokabel["spanisch"], vokabel["deutsch"]


def statische_hilfe(richtige_antwort: str) -> str:
    return (
        f"Tipp ohne KI: Sprich die richtige Antwort laut vor: '{richtige_antwort}'. "
        "Schreib sie dreimal und verknüpfe sie mit einer Situation (z. B. beim Vermieter)."
    )


def runde(vokabeln: list[dict[str, str]], richtung: str) -> None:
    zufall = vokabeln.copy()
    random.shuffle(zufall)
    richtig = 0
    gesamt = len(zufall)

    richtung_text = "Deutsch -> Spanisch" if richtung == "de->es" else "Spanisch -> Deutsch"
    print(f"\n--- Runde: {gesamt} Vokabeln ({richtung_text}) ---")
    print("Leere Eingabe oder «überspringen» = nächste Vokabel\n")

    for nr, vok in enumerate(zufall, start=1):
        frage, loesung = frage_stellen(vok, richtung)
        print(f"[{nr}/{gesamt}] {frage}")
        eingabe = input("Deine Antwort: ").strip()

        if not eingabe or normalisiere(eingabe) == "uberspringen":
            print(f"  -> Übersprungen. Lösung: {loesung}\n")
            continue

        if ist_richtig(loesung, eingabe):
            richtig += 1
            print("  + Richtig!\n")
            continue

        print(f"  x Falsch. Richtig wäre: {loesung}")
        hilfe = ki_hilfe(frage, loesung, eingabe, richtung_text)
        if hilfe:
            print("\n  --- KI-Merkhilfe ---")
            for zeile in hilfe.splitlines():
                print(f"  {zeile}")
            print("  --------------------\n")
        else:
            print(f"\n  {statische_hilfe(loesung)}")
            print(
                "  Für KI-Eselsbrücken: OPENAI_API_KEY setzen (siehe .env.example).\n"
            )

    print("--- Ergebnis ---")
    print(f"{richtig} von {gesamt} richtig beantwortet.")
    if gesamt:
        prozent = round(100 * richtig / gesamt)
        print(f"Das sind {prozent} %.\n")


def main() -> None:
    konfiguriere_ausgabe()
    lade_env()
    vokabeln = lade_vokabeln()

    print("=" * 50)
    print("  Spanisch-Vokabeltrainer – Auswandern nach Spanien")
    print("=" * 50)
    print(f"Geladen: {len(vokabeln)} Vokabeln aus {VOKABELN_DATEI.name}")

    if not os.environ.get("OPENAI_API_KEY"):
        print(
            "\nHinweis: Ohne OPENAI_API_KEY gibt es bei Fehlern nur kurze Tipps."
            "\nKopiere .env.example nach .env und trage deinen API-Schlüssel ein."
        )
    elif OpenAI is None:
        print("\nHinweis: Paket «openai» fehlt. Installiere mit: pip install -r requirements.txt")

    while True:
        richtung = waehle_richtung()
        runde(vokabeln, richtung)
        nochmal = input("Noch eine Runde? [j/N]: ").strip().lower()
        if nochmal not in ("j", "ja", "y", "yes"):
            print("\n¡Hasta luego! Viel Erfolg in Spanien.")
            break


if __name__ == "__main__":
    main()
