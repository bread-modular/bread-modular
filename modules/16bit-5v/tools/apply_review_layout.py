#!/usr/bin/python3
"""Disabled historical partial prototype; NOT the final saved LX layout.

The canonical final PCB is authoritative. Do not replay the historical incremental
placement/routes. Use verify_power.py for read-only proofs and
regenerate_production.py --review-preparation for final exports (never migration).
"""
raise SystemExit('Replay disabled: preserve the reviewed final power layout; verify/export the saved PCB instead.')
