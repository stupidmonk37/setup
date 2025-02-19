#!/usr/bin/env python3
"""Find connections between chips in a Groq XT topology.

Usage:
  Xc node_arg A B            (two-chip mode)
  Xc node_arg A P<port>      (port mode)
  Xc node_arg A              (all connections mode)

Where:
- Xc: X is one of [8,16,24,32,40,64,72], e.g. '72c'
- node_arg: one of [1, N1, gn1], must map to a start node 1-9
- A: either an integer chip number or a node/card string like 'N8/C7'
- B: either an integer chip number or a node/card string like 'N8/C7'
- P<port>: a port string like 'P0', 'P15' (only in port mode)

Examples:
  72c N1 32 36 (find connections between chip 32 and chip 36)
  72c 1 0 8 (find connections between chip 0 and chip 8)
  72c gn1 N2/C0 N3/C0 (find connections between N2/C0 and N3/C0)
  72c N2 N3/C0 P5 (find connections from N2/C0/P5)
  72c N1 32   (find all connections for chip 32)
"""

import re
import sys
import pathlib

# c.f. https://docs.google.com/document/d/1B5DklmXeH1wdVa2nCzdL8MiHC1i80zjb_jbNmjocq8 p.18

external_connections = [
    {
        "connection_number": 1,
        "side1": "N8/C7/P15",
        "side2": "N9/C7/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 2,
        "side1": "N7/C7/P15",
        "side2": "N8/C7/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 3,
        "side1": "N6/C7/P15",
        "side2": "N7/C7/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 4,
        "side1": "N5/C7/P15",
        "side2": "N6/C7/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 5,
        "side1": "N4/C7/P15",
        "side2": "N5/C7/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 6,
        "side1": "N3/C7/P15",
        "side2": "N4/C7/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 7,
        "side1": "N2/C7/P15",
        "side2": "N3/C7/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 8,
        "side1": "N1/C7/P15",
        "side2": "N2/C7/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 9,
        "side1": "N5/C7/P5",
        "side2": "N9/C7/P0",
        "length": "1.0m",
    },
    {
        "connection_number": 10,
        "side1": "N4/C7/P5",
        "side2": "N8/C7/P0",
        "length": "1.0m",
    },
    {
        "connection_number": 11,
        "side1": "N3/C7/P5",
        "side2": "N7/C7/P0",
        "length": "1.0m",
    },
    {
        "connection_number": 12,
        "side1": "N2/C7/P5",
        "side2": "N6/C7/P0",
        "length": "1.0m",
    },
    {
        "connection_number": 13,
        "side1": "N1/C7/P5",
        "side2": "N5/C7/P0",
        "length": "1.0m",
    },
    {
        "connection_number": 14,
        "side1": "N6/C6/P15",
        "side2": "N9/C6/P4",
        "length": "0.75m",
    },
    {
        "connection_number": 15,
        "side1": "N5/C6/P15",
        "side2": "N8/C6/P4",
        "length": "0.75m",
    },
    {
        "connection_number": 16,
        "side1": "N4/C6/P15",
        "side2": "N7/C6/P4",
        "length": "0.75m",
    },
    {
        "connection_number": 17,
        "side1": "N3/C6/P15",
        "side2": "N6/C6/P4",
        "length": "0.75m",
    },
    {
        "connection_number": 18,
        "side1": "N2/C6/P15",
        "side2": "N5/C6/P4",
        "length": "0.75m",
    },
    {
        "connection_number": 19,
        "side1": "N1/C6/P15",
        "side2": "N4/C6/P4",
        "length": "0.75m",
    },
    {
        "connection_number": 20,
        "side1": "N7/C6/P5",
        "side2": "N9/C6/P0",
        "length": "0.5m",
    },
    {
        "connection_number": 21,
        "side1": "N6/C6/P5",
        "side2": "N8/C6/P0",
        "length": "0.5m",
    },
    {
        "connection_number": 22,
        "side1": "N5/C6/P5",
        "side2": "N7/C6/P0",
        "length": "0.5m",
    },
    {
        "connection_number": 23,
        "side1": "N4/C6/P5",
        "side2": "N6/C6/P0",
        "length": "0.75m",
    },
    {
        "connection_number": 24,
        "side1": "N3/C6/P5",
        "side2": "N5/C6/P0",
        "length": "0.75m",
    },
    {
        "connection_number": 25,
        "side1": "N2/C6/P5",
        "side2": "N4/C6/P0",
        "length": "0.5m",
    },
    {
        "connection_number": 26,
        "side1": "N1/C6/P5",
        "side2": "N3/C6/P0",
        "length": "0.5m",
    },
    {
        "connection_number": 27,
        "side1": "N7/C5/P15",
        "side2": "N9/C5/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 28,
        "side1": "N6/C5/P15",
        "side2": "N8/C5/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 29,
        "side1": "N5/C5/P15",
        "side2": "N7/C5/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 30,
        "side1": "N4/C5/P15",
        "side2": "N6/C5/P4",
        "length": "0.75m",
    },
    {
        "connection_number": 31,
        "side1": "N3/C5/P15",
        "side2": "N5/C5/P4",
        "length": "0.75m",
    },
    {
        "connection_number": 32,
        "side1": "N2/C5/P15",
        "side2": "N4/C5/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 33,
        "side1": "N1/C5/P15",
        "side2": "N3/C5/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 34,
        "side1": "N5/C5/P5",
        "side2": "N9/C5/P0",
        "length": "1.0m",
    },
    {
        "connection_number": 35,
        "side1": "N4/C5/P5",
        "side2": "N8/C5/P0",
        "length": "1.0m",
    },
    {
        "connection_number": 36,
        "side1": "N3/C5/P5",
        "side2": "N7/C5/P0",
        "length": "1.0m",
    },
    {
        "connection_number": 37,
        "side1": "N2/C5/P5",
        "side2": "N6/C5/P0",
        "length": "1.0m",
    },
    {
        "connection_number": 38,
        "side1": "N1/C5/P5",
        "side2": "N5/C5/P0",
        "length": "1.0m",
    },
    {
        "connection_number": 39,
        "side1": "N8/C4/P15",
        "side2": "N9/C4/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 40,
        "side1": "N7/C4/P15",
        "side2": "N8/C4/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 41,
        "side1": "N6/C4/P15",
        "side2": "N7/C4/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 42,
        "side1": "N5/C4/P15",
        "side2": "N6/C4/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 43,
        "side1": "N4/C4/P15",
        "side2": "N5/C4/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 44,
        "side1": "N3/C4/P15",
        "side2": "N4/C4/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 45,
        "side1": "N2/C4/P15",
        "side2": "N3/C4/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 46,
        "side1": "N1/C4/P15",
        "side2": "N2/C4/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 47,
        "side1": "N6/C4/P5",
        "side2": "N9/C4/P0",
        "length": "0.75m",
    },
    {
        "connection_number": 48,
        "side1": "N5/C4/P5",
        "side2": "N8/C4/P0",
        "length": "0.75m",
    },
    {
        "connection_number": 49,
        "side1": "N4/C4/P5",
        "side2": "N7/C4/P0",
        "length": "0.75m",
    },
    {
        "connection_number": 50,
        "side1": "N3/C4/P5",
        "side2": "N6/C4/P0",
        "length": "0.75m",
    },
    {
        "connection_number": 51,
        "side1": "N2/C4/P5",
        "side2": "N5/C4/P0",
        "length": "0.75m",
    },
    {
        "connection_number": 52,
        "side1": "N1/C4/P5",
        "side2": "N4/C4/P0",
        "length": "0.75m",
    },
    {
        "connection_number": 53,
        "side1": "N6/C3/P15",
        "side2": "N9/C3/P4",
        "length": "0.75m",
    },
    {
        "connection_number": 54,
        "side1": "N5/C3/P15",
        "side2": "N8/C3/P4",
        "length": "0.75m",
    },
    {
        "connection_number": 55,
        "side1": "N4/C3/P15",
        "side2": "N7/C3/P4",
        "length": "0.75m",
    },
    {
        "connection_number": 56,
        "side1": "N3/C3/P15",
        "side2": "N6/C3/P4",
        "length": "0.75m",
    },
    {
        "connection_number": 57,
        "side1": "N2/C3/P15",
        "side2": "N5/C3/P4",
        "length": "0.75m",
    },
    {
        "connection_number": 58,
        "side1": "N1/C3/P15",
        "side2": "N4/C3/P4",
        "length": "0.75m",
    },
    {
        "connection_number": 59,
        "side1": "N5/C3/P5",
        "side2": "N9/C3/P0",
        "length": "1.0m",
    },
    {
        "connection_number": 60,
        "side1": "N4/C3/P5",
        "side2": "N8/C3/P0",
        "length": "1.0m",
    },
    {
        "connection_number": 61,
        "side1": "N3/C3/P5",
        "side2": "N7/C3/P0",
        "length": "1.0m",
    },
    {
        "connection_number": 62,
        "side1": "N2/C3/P5",
        "side2": "N6/C3/P0",
        "length": "1.0m",
    },
    {
        "connection_number": 63,
        "side1": "N1/C3/P5",
        "side2": "N5/C3/P0",
        "length": "1.0m",
    },
    {
        "connection_number": 64,
        "side1": "N8/C2/P15",
        "side2": "N9/C2/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 65,
        "side1": "N7/C2/P15",
        "side2": "N8/C2/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 66,
        "side1": "N6/C2/P15",
        "side2": "N7/C2/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 67,
        "side1": "N5/C2/P15",
        "side2": "N6/C2/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 68,
        "side1": "N4/C2/P15",
        "side2": "N5/C2/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 69,
        "side1": "N3/C2/P15",
        "side2": "N4/C2/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 70,
        "side1": "N2/C2/P15",
        "side2": "N3/C2/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 71,
        "side1": "N1/C2/P15",
        "side2": "N2/C2/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 72,
        "side1": "N7/C2/P5",
        "side2": "N9/C2/P0",
        "length": "0.5m",
    },
    {
        "connection_number": 73,
        "side1": "N6/C2/P5",
        "side2": "N8/C2/P0",
        "length": "0.5m",
    },
    {
        "connection_number": 74,
        "side1": "N5/C2/P5",
        "side2": "N7/C2/P0",
        "length": "0.5m",
    },
    {
        "connection_number": 75,
        "side1": "N4/C2/P5",
        "side2": "N6/C2/P0",
        "length": "0.75m",
    },
    {
        "connection_number": 76,
        "side1": "N3/C2/P5",
        "side2": "N5/C2/P0",
        "length": "0.5m",
    },
    {
        "connection_number": 77,
        "side1": "N2/C2/P5",
        "side2": "N4/C2/P0",
        "length": "0.5m",
    },
    {
        "connection_number": 78,
        "side1": "N1/C2/P5",
        "side2": "N3/C2/P0",
        "length": "0.5m",
    },
    {
        "connection_number": 79,
        "side1": "N6/C1/P15",
        "side2": "N9/C1/P4",
        "length": "0.75m",
    },
    {
        "connection_number": 80,
        "side1": "N5/C1/P15",
        "side2": "N8/C1/P4",
        "length": "0.75m",
    },
    {
        "connection_number": 81,
        "side1": "N4/C1/P15",
        "side2": "N7/C1/P4",
        "length": "0.75m",
    },
    {
        "connection_number": 82,
        "side1": "N3/C1/P15",
        "side2": "N6/C1/P4",
        "length": "0.75m",
    },
    {
        "connection_number": 83,
        "side1": "N2/C1/P15",
        "side2": "N5/C1/P4",
        "length": "0.75m",
    },
    {
        "connection_number": 84,
        "side1": "N1/C1/P15",
        "side2": "N4/C1/P4",
        "length": "0.75m",
    },
    {
        "connection_number": 85,
        "side1": "N5/C1/P5",
        "side2": "N9/C1/P0",
        "length": "1.0m",
    },
    {
        "connection_number": 86,
        "side1": "N4/C1/P5",
        "side2": "N8/C1/P0",
        "length": "1.0m",
    },
    {
        "connection_number": 87,
        "side1": "N3/C1/P5",
        "side2": "N7/C1/P0",
        "length": "1.0m",
    },
    {
        "connection_number": 88,
        "side1": "N2/C1/P5",
        "side2": "N6/C1/P0",
        "length": "1.0m",
    },
    {
        "connection_number": 89,
        "side1": "N1/C1/P5",
        "side2": "N5/C1/P0",
        "length": "1.0m",
    },
    {
        "connection_number": 90,
        "side1": "N7/C0/P15",
        "side2": "N9/C0/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 91,
        "side1": "N6/C0/P15",
        "side2": "N8/C0/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 92,
        "side1": "N5/C0/P15",
        "side2": "N7/C0/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 93,
        "side1": "N4/C0/P15",
        "side2": "N6/C0/P4",
        "length": "0.75m",
    },
    {
        "connection_number": 94,
        "side1": "N3/C0/P15",
        "side2": "N5/C0/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 95,
        "side1": "N2/C0/P15",
        "side2": "N4/C0/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 96,
        "side1": "N1/C0/P15",
        "side2": "N3/C0/P4",
        "length": "0.5m",
    },
    {
        "connection_number": 97,
        "side1": "N8/C0/P5",
        "side2": "N9/C0/P0",
        "length": "0.5m",
    },
    {
        "connection_number": 98,
        "side1": "N7/C0/P5",
        "side2": "N8/C0/P0",
        "length": "0.5m",
    },
    {
        "connection_number": 99,
        "side1": "N6/C0/P5",
        "side2": "N7/C0/P0",
        "length": "0.5m",
    },
    {
        "connection_number": 100,
        "side1": "N5/C0/P5",
        "side2": "N6/C0/P0",
        "length": "0.5m",
    },
    {
        "connection_number": 101,
        "side1": "N4/C0/P5",
        "side2": "N5/C0/P0",
        "length": "0.5m",
    },
    {
        "connection_number": 102,
        "side1": "N3/C0/P5",
        "side2": "N4/C0/P0",
        "length": "0.5m",
    },
    {
        "connection_number": 103,
        "side1": "N2/C0/P5",
        "side2": "N3/C0/P0",
        "length": "0.5m",
    },
    {
        "connection_number": 104,
        "side1": "N1/C0/P5",
        "side2": "N2/C0/P0",
        "length": "0.5m",
    },
    # c.f. https://docs.google.com/document/d/1B5DklmXeH1wdVa2nCzdL8MiHC1i80zjb_jbNmjocq8 p.22
    {
        "connection_number": 105,
        "side1": "N9/C1/P5",
        "side2": "Next N4/C1/P0",
        "length": "2.75m",
    },
    {
        "connection_number": 106,
        "side1": "N9/C1/P15",
        "side2": "Next N3/C1/P4",
        "length": "2.75m",
    },
    {
        "connection_number": 107,
        "side1": "N9/C3/P5",
        "side2": "Next N4/C3/P0",
        "length": "2.75m",
    },
    {
        "connection_number": 108,
        "side1": "N9/C3/P15",
        "side2": "Next N3/C3/P4",
        "length": "2.75m",
    },
    {
        "connection_number": 109,
        "side1": "N9/C4/P5",
        "side2": "Next N3/C4/P0",
        "length": "2.75m",
    },
    {
        "connection_number": 110,
        "side1": "N9/C5/P5",
        "side2": "Next N4/C5/P0",
        "length": "2.75m",
    },
    {
        "connection_number": 111,
        "side1": "N9/C7/P5",
        "side2": "Next N4/C7/P0",
        "length": "2.75m",
    },
    {
        "connection_number": 112,
        "side1": "N8/C1/P5",
        "side2": "Next N3/C1/P0",
        "length": "3m",
    },
    {
        "connection_number": 113,
        "side1": "N8/C3/P5",
        "side2": "Next N3/C3/P0",
        "length": "3m",
    },
    {
        "connection_number": 114,
        "side1": "N8/C3/P15",
        "side2": "Next N2/C3/P4",
        "length": "3m",
    },
    {
        "connection_number": 115,
        "side1": "N8/C4/P5",
        "side2": "Next N2/C4/P0",
        "length": "3m",
    },
    {
        "connection_number": 116,
        "side1": "N8/C5/P5",
        "side2": "Next N3/C5/P0",
        "length": "3m",
    },
    {
        "connection_number": 117,
        "side1": "N8/C7/P5",
        "side2": "Next N3/C7/P0",
        "length": "3m",
    },
    {
        "connection_number": 118,
        "side1": "N9/C0/P15",
        "side2": "Next N2/C0/P4",
        "length": "3m",
    },
    {
        "connection_number": 119,
        "side1": "N9/C2/P5",
        "side2": "Next N2/C2/P0",
        "length": "3m",
    },
    {
        "connection_number": 120,
        "side1": "N9/C5/P15",
        "side2": "Next N2/C5/P4",
        "length": "3m",
    },
    {
        "connection_number": 121,
        "side1": "N9/C6/P5",
        "side2": "Next N2/C6/P0",
        "length": "3m",
    },
    {
        "connection_number": 122,
        "side1": "N9/C6/P15",
        "side2": "Next N3/C6/P4",
        "length": "3m",
    },
    {
        "connection_number": 123,
        "side1": "N8/C0/P15",
        "side2": "Next N1/C0/P4",
        "length": "3.25m",
    },
    {
        "connection_number": 124,
        "side1": "N8/C1/P15",
        "side2": "Next N2/C1/P4",
        "length": "3.25m",
    },
    {
        "connection_number": 125,
        "side1": "N8/C2/P5",
        "side2": "Next N1/C2/P0",
        "length": "3.25m",
    },
    {
        "connection_number": 126,
        "side1": "N8/C5/P15",
        "side2": "Next N1/C5/P4",
        "length": "3.25m",
    },
    {
        "connection_number": 127,
        "side1": "N8/C6/P5",
        "side2": "Next N1/C6/P0",
        "length": "3.25m",
    },
    {
        "connection_number": 128,
        "side1": "N8/C6/P15",
        "side2": "Next N2/C6/P4",
        "length": "3.25m",
    },
    {
        "connection_number": 129,
        "side1": "N9/C0/P5",
        "side2": "Next N1/C0/P0",
        "length": "3.25m",
    },
    {
        "connection_number": 130,
        "side1": "N9/C2/P15",
        "side2": "Next N1/C2/P4",
        "length": "3.25m",
    },
    {
        "connection_number": 131,
        "side1": "N9/C4/P15",
        "side2": "Next N1/C4/P4",
        "length": "3.25m",
    },
    {
        "connection_number": 132,
        "side1": "N9/C7/P15",
        "side2": "Next N1/C7/P4",
        "length": "3.25m",
    },
    {
        "connection_number": 133,
        "side1": "N7/C1/P5",
        "side2": "Next N2/C1/P0",
        "length": "3.5m",
    },
    {
        "connection_number": 134,
        "side1": "N7/C1/P15",
        "side2": "Next N1/C1/P4",
        "length": "3.5m",
    },
    {
        "connection_number": 135,
        "side1": "N7/C3/P5",
        "side2": "Next N2/C3/P0",
        "length": "3.5m",
    },
    {
        "connection_number": 136,
        "side1": "N7/C3/P15",
        "side2": "Next N1/C3/P4",
        "length": "3.5m",
    },
    {
        "connection_number": 137,
        "side1": "N7/C4/P5",
        "side2": "Next N1/C4/P0",
        "length": "3.5m",
    },
    {
        "connection_number": 138,
        "side1": "N7/C5/P5",
        "side2": "Next N2/C5/P0",
        "length": "3.5m",
    },
    {
        "connection_number": 139,
        "side1": "N7/C6/P15",
        "side2": "Next N1/C6/P4",
        "length": "3.5m",
    },
    {
        "connection_number": 140,
        "side1": "N7/C7/P5",
        "side2": "Next N2/C7/P0",
        "length": "3.5m",
    },
    {
        "connection_number": 141,
        "side1": "N6/C1/P5",
        "side2": "Next N1/C1/P0",
        "length": "3.75m",
    },
    {
        "connection_number": 142,
        "side1": "N6/C3/P5",
        "side2": "Next N1/C3/P0",
        "length": "3.75m",
    },
    {
        "connection_number": 143,
        "side1": "N6/C5/P5",
        "side2": "Next N1/C5/P0",
        "length": "3.75m",
    },
    {
        "connection_number": 144,
        "side1": "N6/C7/P5",
        "side2": "Next N1/C7/P0",
        "length": "3.75m",
    },
]

internal_connections = [
    {"card1": 3, "connector1": 11, "card2": 1, "connector2": 11},
    {"card1": 3, "connector1": 6, "card2": 2, "connector2": 12},
    {"card1": 3, "connector1": 7, "card2": 0, "connector2": 14},
    {"card1": 2, "connector1": 14, "card2": 1, "connector2": 12},
    {"card1": 2, "connector1": 7, "card2": 0, "connector2": 13},
    {"card1": 1, "connector1": 6, "card2": 0, "connector2": 12},
    {"card1": 7, "connector1": 11, "card2": 5, "connector2": 11},
    {"card1": 7, "connector1": 6, "card2": 6, "connector2": 12},
    {"card1": 7, "connector1": 7, "card2": 4, "connector2": 14},
    {"card1": 6, "connector1": 14, "card2": 5, "connector2": 12},
    {"card1": 6, "connector1": 7, "card2": 4, "connector2": 13},
    {"card1": 5, "connector1": 6, "card2": 4, "connector2": 12},
    {"card1": 7, "connector1": 14, "card2": 2, "connector2": 13},
    {"card1": 7, "connector1": 13, "card2": 3, "connector2": 13},
    {"card1": 7, "connector1": 12, "card2": 1, "connector2": 13},
    {"card1": 7, "connector1": 8, "card2": 0, "connector2": 11},
    {"card1": 6, "connector1": 13, "card2": 3, "connector2": 14},
    {"card1": 6, "connector1": 11, "card2": 1, "connector2": 14},
    {"card1": 6, "connector1": 6, "card2": 2, "connector2": 6},
    {"card1": 6, "connector1": 8, "card2": 0, "connector2": 6},
    {"card1": 5, "connector1": 14, "card2": 2, "connector2": 11},
    {"card1": 5, "connector1": 13, "card2": 3, "connector2": 12},
    {"card1": 5, "connector1": 7, "card2": 1, "connector2": 7},
    {"card1": 5, "connector1": 8, "card2": 0, "connector2": 7},
    {"card1": 4, "connector1": 11, "card2": 3, "connector2": 8},
    {"card1": 4, "connector1": 7, "card2": 1, "connector2": 8},
    {"card1": 4, "connector1": 6, "card2": 2, "connector2": 8},
    {"card1": 4, "connector1": 8, "card2": 0, "connector2": 8},
]


def parse_side(side_str):
    """
    Parse a side string such as:
      "N9/C1/P5"         -> (rack='RX',   node='N9', card='C1', port='P5')
      "Next N3/C4/P0"    -> (rack='RX+1', node='N3', card='C4', port='P0')
    """
    if side_str.startswith("Next "):
        rack = "RX+1"
        rest = side_str[5:]
    else:
        rack = "RX"
        rest = side_str

    node, card, port = rest.split("/")
    return rack, node, card, port


def parse_node_arg(node_arg):
    # node_arg can be '1', 'N1', or 'gn1' → numeric node 1..9
    raw = node_arg
    if raw.startswith("gn"):
        raw = raw[2:]
    if raw.startswith("N"):
        raw = raw[1:]
    try:
        start_node_num = int(raw)
    except ValueError:
        raise ValueError("Node argument must be a number, or N<number>, or gn<number>.")
    if not (1 <= start_node_num <= 9):
        raise ValueError("Start node must be between 1 and 9.")
    return start_node_num


def map_chip_to_node_card(chip, start_node_num):
    """
    Map a chip index (0..(nchips-1)) to a node/card pair
    given the 'start_node_num'.
    """
    node_num = (((chip // 8) + (start_node_num - 1)) % 9) + 1
    card_num = chip % 8
    return node_num, card_num


def node_card_to_chip(node_num, card_num, start_node_num, nchips):
    """
    Reverse lookup: given a node_num + card_num → which chip index is it?
    Return None if not found in [0..nchips-1].
    """
    for candidate_chip in range(nchips):
        n_num, c_num = map_chip_to_node_card(candidate_chip, start_node_num)
        if n_num == node_num and c_num == card_num:
            return candidate_chip
    return None


def print_connection(rackA, nA, cA, pA, devA, rackB, nB, cB, pB, devB):
    """
    Print a connection with the format:
        RX/N6/C5/P5 (dev X) ↔ RX+1/N1/C5/P0 (dev Y)
    """
    print(f"{rackA}/{nA}/{cA}/{pA} (dev {devA}) ↔ {rackB}/{nB}/{cB}/{pB} (dev {devB})")


def find_all_connections_for_chip(nchips, start_node_num, A_chip):
    connections = []
    nA, cA = map_chip_to_node_card(A_chip, start_node_num)

    for conn in internal_connections:
        if conn["card1"] == cA:
            other_card = conn["card2"]
            other_connector = conn["connector2"]
            connector = conn["connector1"]
            other_chip = node_card_to_chip(nA, other_card, start_node_num, nchips)
            if other_chip is not None:
                connections.append((
                    connector,
                    "RX",
                    f"N{nA}",
                    f"C{cA}",
                    A_chip,
                    "RX",
                    f"N{nA}",
                    f"C{other_card}",
                    other_connector,
                    other_chip,
                ))
        elif conn["card2"] == cA:
            other_card = conn["card1"]
            other_connector = conn["connector1"]
            connector = conn["connector2"]
            other_chip = node_card_to_chip(nA, other_card, start_node_num, nchips)
            if other_chip is not None:
                connections.append((
                    connector,
                    "RX",
                    f"N{nA}",
                    f"C{cA}",
                    A_chip,
                    "RX",
                    f"N{nA}",
                    f"C{other_card}",
                    other_connector,
                    other_chip,
                ))

    for conn in external_connections:
        s1_rack, s1_node, s1_card, s1_port = parse_side(conn["side1"])
        s2_rack, s2_node, s2_card, s2_port = parse_side(conn["side2"])

        s1_node_num = int(s1_node[1:])
        s1_card_num = int(s1_card[1:])
        s2_node_num = int(s2_node[1:])
        s2_card_num = int(s2_card[1:])
        p1 = int(s1_port[1:])
        p2 = int(s2_port[1:])

        if s1_node_num == nA and s1_card_num == cA:
            other_chip = node_card_to_chip(
                s2_node_num, s2_card_num, start_node_num, nchips
            )
            if other_chip is not None:
                connections.append((
                    p1,
                    s1_rack,
                    s1_node,
                    s1_card,
                    A_chip,
                    s2_rack,
                    s2_node,
                    s2_card,
                    p2,
                    other_chip,
                ))
        elif s2_node_num == nA and s2_card_num == cA:
            other_chip = node_card_to_chip(
                s1_node_num, s1_card_num, start_node_num, nchips
            )
            if other_chip is not None:
                connections.append((
                    p2,
                    s2_rack,
                    s2_node,
                    s2_card,
                    A_chip,
                    s1_rack,
                    s1_node,
                    s1_card,
                    p1,
                    other_chip,
                ))

    connections.sort(key=lambda x: x[0])
    return connections


def find_connections_between_chips(nchips, start_node_num, A_chip, B_chip):
    connections = []
    nA, cA = map_chip_to_node_card(A_chip, start_node_num)
    nB, cB = map_chip_to_node_card(B_chip, start_node_num)

    if nA == nB:
        for conn in internal_connections:
            if conn["card1"] == cA and conn["card2"] == cB:
                connections.append((
                    conn["connector1"],
                    "RX",
                    f"N{nA}",
                    f"C{cA}",
                    A_chip,
                    "RX",
                    f"N{nB}",
                    f"C{cB}",
                    conn["connector2"],
                    B_chip,
                ))
            elif conn["card2"] == cA and conn["card1"] == cB:
                connections.append((
                    conn["connector2"],
                    "RX",
                    f"N{nA}",
                    f"C{cA}",
                    A_chip,
                    "RX",
                    f"N{nB}",
                    f"C{cB}",
                    conn["connector1"],
                    B_chip,
                ))
    else:
        for conn in external_connections:
            s1_rack, s1_node, s1_card, s1_port = parse_side(conn["side1"])
            s2_rack, s2_node, s2_card, s2_port = parse_side(conn["side2"])

            s1_node_num = int(s1_node[1:])
            s1_card_num = int(s1_card[1:])
            s2_node_num = int(s2_node[1:])
            s2_card_num = int(s2_card[1:])
            p1 = int(s1_port[1:])
            p2 = int(s2_port[1:])

            if (
                s1_node_num == nA
                and s1_card_num == cA
                and s2_node_num == nB
                and s2_card_num == cB
            ):
                connections.append((
                    p1,
                    s1_rack,
                    s1_node,
                    s1_card,
                    A_chip,
                    s2_rack,
                    s2_node,
                    s2_card,
                    p2,
                    B_chip,
                ))
            elif (
                s2_node_num == nA
                and s2_card_num == cA
                and s1_node_num == nB
                and s1_card_num == cB
            ):
                connections.append((
                    p2,
                    s2_rack,
                    s2_node,
                    s2_card,
                    A_chip,
                    s1_rack,
                    s1_node,
                    s1_card,
                    p1,
                    B_chip,
                ))

    connections.sort(key=lambda x: x[0])
    return connections


def c2c_internal_connections_by_port(card, connector):
    """
    Returns all internal links from (card, connector).
    """
    results = []
    for conn in internal_connections:
        if conn["card1"] == card and conn["connector1"] == connector:
            results.append((card, connector, conn["card2"], conn["connector2"]))
        elif conn["card2"] == card and conn["connector2"] == connector:
            results.append((card, connector, conn["card1"], conn["connector1"]))
    return results


def find_connections_from_port(nchips, start_node_num, A_chip, port_str):
    connections = []
    nA, cA = map_chip_to_node_card(A_chip, start_node_num)
    port_num = int(port_str[1:])

    internal_matches = c2c_internal_connections_by_port(cA, port_num)
    for card, connector, other_card, other_connector in internal_matches:
        other_chip = node_card_to_chip(nA, other_card, start_node_num, nchips)
        if other_chip is not None:
            connections.append((
                connector,
                "RX",
                f"N{nA}",
                f"C{cA}",
                A_chip,
                "RX",
                f"N{nA}",
                f"C{other_card}",
                other_connector,
                other_chip,
            ))

    for conn in external_connections:
        s1_rack, s1_node, s1_card, s1_port = parse_side(conn["side1"])
        s2_rack, s2_node, s2_card, s2_port = parse_side(conn["side2"])

        s1_node_num = int(s1_node[1:])
        s1_card_num = int(s1_card[1:])
        s2_node_num = int(s2_node[1:])
        s2_card_num = int(s2_card[1:])
        p1 = int(s1_port[1:])
        p2 = int(s2_port[1:])

        if s1_node_num == nA and s1_card_num == cA and p1 == port_num:
            other_chip = node_card_to_chip(
                s2_node_num, s2_card_num, start_node_num, nchips
            )
            if other_chip is not None:
                connections.append((
                    p1,
                    s1_rack,
                    s1_node,
                    s1_card,
                    A_chip,
                    s2_rack,
                    s2_node,
                    s2_card,
                    p2,
                    other_chip,
                ))
        elif s2_node_num == nA and s2_card_num == cA and p2 == port_num:
            other_chip = node_card_to_chip(
                s1_node_num, s1_card_num, start_node_num, nchips
            )
            if other_chip is not None:
                connections.append((
                    p2,
                    s2_rack,
                    s2_node,
                    s2_card,
                    A_chip,
                    s1_rack,
                    s1_node,
                    s1_card,
                    p1,
                    other_chip,
                ))

    connections.sort(key=lambda x: x[0])
    return connections


def parse_chip_arg(arg, nchips, start_node_num):
    """
    A chip arg can be '36' or 'N4/C3'
    """
    try:
        chip_int = int(arg)
        return chip_int
    except ValueError:
        if "/" not in arg:
            raise ValueError(
                "Chip argument must be either int or 'N<number>/C<number>'."
            )
        node_str, card_str = arg.split("/")
        if not (node_str.startswith("N") and card_str.startswith("C")):
            raise ValueError("Chip argument must be 'N<number>/C<number>'.")
        try:
            node_num = int(node_str[1:])
            card_num = int(card_str[1:])
        except ValueError:
            raise ValueError("Invalid node/card numbers in chip argument.")
        chip = node_card_to_chip(node_num, card_num, start_node_num, nchips)
        if chip is None:
            raise ValueError(
                "No chip matches the given node/card under current mapping."
            )
        return chip


def validate_nchips(nchips: str) -> bool:
    """
    e.g. '8c', '16c', '24c', '32c', '40c', '64c', '72c'
    """
    pattern = r"^(8|16|24|32|40|64|72)c?$"
    return bool(re.match(pattern, nchips))


def get_nchips(nchips: str) -> int:
    return int(re.match(r"(\d+)", nchips).group(1))


def main():
    script_name = pathlib.Path(sys.argv[0]).name

    if len(sys.argv) < 4:
        print("Usage:")
        print(f"\t{script_name} [nchips] [start_node] [chip_0] [chip_1]")
        print(f"\t{script_name} [nchips] [start_node] [chip_0] P<port>")
        print(f"\t{script_name} [nchips] [start_node] [chip_0]")
        print("\nExamples:")
        print(
            f"\t{script_name} 72c N1 32 36 (find connections between chip 32 and chip 36)"
        )
        print(f"\t{script_name} 72c 1 0 8 (find connections between chip 0 and chip 8)")
        print(
            f"\t{script_name} 72c gn1 N2/C0 N3/C0 (find connections between N2/C0 and N3/C0)"
        )
        print(f"\t{script_name} 72c N2 N3/C0 P5 (find connections from N2/C0/P5)")
        print(f"\t{script_name} 72c N1 32 (find all connections for chip 32)")
        return

    x_arg = sys.argv[1]
    n_arg = sys.argv[2]

    if validate_nchips(x_arg):
        nchips = get_nchips(x_arg)
    else:
        print(f"Error: nchips must be in format [8|16|24|32|40|64|72]c?, got {x_arg}")
        return

    try:
        start_node_num = parse_node_arg(n_arg)
    except ValueError as err:
        print(err)
        return

    A_arg = sys.argv[3]

    if len(sys.argv) == 5:
        B_arg = sys.argv[4]
        if B_arg.startswith("P"):
            try:
                A_chip = parse_chip_arg(A_arg, nchips, start_node_num)
            except ValueError as e:
                print(e)
                return
            if not (0 <= A_chip < nchips):
                print(f"Chip numbers must be between 0 and {nchips - 1}.")
                return
            connections = find_connections_from_port(
                nchips, start_node_num, A_chip, B_arg
            )
        else:
            try:
                A_chip = parse_chip_arg(A_arg, nchips, start_node_num)
                B_chip = parse_chip_arg(B_arg, nchips, start_node_num)
            except ValueError as e:
                print(e)
                return
            if not (0 <= A_chip < nchips and 0 <= B_chip < nchips):
                print(f"Chip numbers must be between 0 and {nchips - 1}.")
                return
            connections = find_connections_between_chips(
                nchips, start_node_num, A_chip, B_chip
            )
    elif len(sys.argv) == 4:
        try:
            A_chip = parse_chip_arg(A_arg, nchips, start_node_num)
        except ValueError as e:
            print(e)
            return
        if not (0 <= A_chip < nchips):
            print(f"Chip numbers must be between 0 and {nchips - 1}.")
            return
        connections = find_all_connections_for_chip(nchips, start_node_num, A_chip)
    else:
        print("Invalid arguments. Must provide another chip, a port, or a single chip.")
        return

    for (
        portA,
        rackA,
        nodeA,
        cardA,
        devA,
        rackB,
        nodeB,
        cardB,
        portB,
        devB,
    ) in connections:
        print_connection(
            rackA,
            nodeA,
            cardA,
            f"P{portA}",
            devA,
            rackB,
            nodeB,
            cardB,
            f"P{portB}",
            devB,
        )


if __name__ == "__main__":
    main()
