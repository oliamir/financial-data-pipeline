"""Tests for the company universe and priority list data layer."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from src.universe.universe import (
    TASECompany,
    _normalise_sector,
    search_companies,
    PriorityList,
    save_universe,
    load_universe,
)


def test_sector_normalisation():
    """Verify raw TASE sectors are cleanly mapped."""
    assert _normalise_sector("High-Tech-Technology-Renewable Energy") == "Renewable Energy"
    assert _normalise_sector("High-Tech-Technology-Software And Internet") == "Software & Internet"
    assert _normalise_sector("Real-Real-Estate & Construction-Construction") == "Construction"
    assert _normalise_sector(None) == "Other"
    assert _normalise_sector("") == "Other"
    # Fallback test
    assert _normalise_sector("Unknown-Category-Weird") == "Category - Weird"


def test_search_companies():
    """Verify company filtering works."""
    c1 = TASECompany(name="SOFWAVE MEDICAL", full_name="SOFWAVE LTD", sector="Medical Devices")
    c2 = TASECompany(name="ENLIGHT ENERGY", full_name="ENLIGHT RENEWABLE", sector="Renewable Energy")
    c3 = TASECompany(name="APOLLO POWER", full_name="APOLLO LTD", sector="Cleantech")
    universe = [c1, c2, c3]

    assert len(search_companies(universe, query="sof")) == 1
    assert search_companies(universe, query="sof")[0].name == "SOFWAVE MEDICAL"
    
    assert len(search_companies(universe, sector="Renewable Energy")) == 1
    assert search_companies(universe, sector="Renewable Energy")[0].name == "ENLIGHT ENERGY"
    
    # Query across full name
    assert len(search_companies(universe, query="ltd")) == 2

    # Query + Sector
    assert len(search_companies(universe, query="enlight", sector="Renewable Energy")) == 1
    assert len(search_companies(universe, query="enlight", sector="Cleantech")) == 0


def test_priority_list_management():
    """Verify adding/removing companies and sectors in PriorityList."""
    with TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir) / "priority.json"
        
        c1 = TASECompany(name="A", sector="Tech")
        c2 = TASECompany(name="B", sector="Tech")
        c3 = TASECompany(name="C", sector="Energy")
        universe = [c1, c2, c3]

        pl = PriorityList(path=tmp)
        assert pl.count() == 0

        # Add single
        assert pl.add_company("A") is True
        assert pl.add_company("A") is False  # Already added
        assert pl.has_company("A") is True
        assert pl.count() == 1

        # Add sector
        added = pl.add_sector("Tech", universe)
        assert added == 1  # B is added, A was already there
        assert pl.has_company("B") is True
        assert pl.has_sector("Tech") is True
        assert pl.count() == 2

        # Remove sector
        removed = pl.remove_sector("Tech", universe)
        assert removed == 2  # A and B removed
        assert pl.has_company("A") is False
        assert pl.has_company("B") is False
        assert pl.count() == 0

        # Verify persistence
        pl.add_company("C")
        pl2 = PriorityList(path=tmp)
        assert pl2.has_company("C") is True
