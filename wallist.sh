#!/usr/bin/env bash
# Startet wallist; mit Stil-KI-Umgebung, falls eingerichtet (~/.local/share/wallist/setup-ki.sh)
d=$HOME/.local/share/wallist
py=$d/venv/bin/python
[ -x "$py" ] || py=python3
exec "$py" "$d/wallist.py" "$@"
