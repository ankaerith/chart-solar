"""Tariff billing: TOU + tiered + export-credit (NEM 3.0 / NBT, SEG, Agile).

Phase 1a: produces hourly bill components from production - consumption +
import/export rules. NEM 3.0 (CA) hourly export credits from CPUC ACC;
UK SEG export-rate picker; flat-rate fallback for everywhere else.
"""
