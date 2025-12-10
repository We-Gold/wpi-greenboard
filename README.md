# WPI Greenboard

This is the codebase for the WPI Greenboard project from CS 542 (Fall 2025).

WPI Greenboard is a carbon emissions tracker for WPI students and majors, based on packages delivered to the school.

Note: This is NOT an official WPI application.

### Team

- Noah Cyr
- Weaver Goldman
- Surbhi Kapoor
- Willem van Oosterum

### Report and Presentation

Report: https://docs.google.com/document/d/1EOGWwAFm53663z2HCClxzTVAIwcJ3VFSNSnHkpRXNFM/edit?usp=sharing

Presentation: https://docs.google.com/presentation/d/1_jIOICF67aSgnaSm4fm3IwPEa1fRt-5s/edit?usp=sharing&ouid=112144393606313004477&rtpof=true&sd=true

### Demo Videos

Primary Demo Video: https://drive.google.com/file/d/1pKzOz-jFmtVVJCR2oNqMlbpQ4OLl4k4Y/preview

Carrier Statistics Demo: https://drive.google.com/file/d/1WbYMLhezAD10zno0leaFz2j0cr24_n7A/preview

Add Package Demo: https://drive.google.com/file/d/10Dit-Oafi9MOzcXofP1Qni_GiDoxT1Nz/preview


## Development

We are using `uv` for managing the Python project. 

Install `uv`: https://docs.astral.sh/uv/getting-started/installation/

From inside this folder:

Build venv (installs packages): `uv sync`

Run main.py: `uv run streamlit run src/greenboard/main.py`

Or: `./dev.sh` (may have to do `chmod +x dev.sh` first)

To add a package, use `uv add <package-name>`. DO NOT pip install it!

To activate the environment in VSCode, follow these instructions: [astral-sh/uv#9637](https://github.com/astral-sh/uv/issues/9637)

### Running with Docker

Easy: `./docker.sh` (may have to do `chmod +x docker.sh` first)

Build: `docker compose build`

Run: `docker compose up`

Stop: `docker compose down`

