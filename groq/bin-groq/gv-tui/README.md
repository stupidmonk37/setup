README.md

What is 'gv_tui'?:
    An app that displays groq validation status in the forms of cluster, node, rack and crossrack.

Starting 'gv_tui':
    - Navigate to '/dc-tools/tools/gv-tui'.
    - Run 'setup.sh'. This will create a python virtual environment and install the required packages.
    - Copy the last line of the output from 'setup.sh' (source gv_tui_venv/bin/activate && python3 gv_tui.py)
      and paste it in a bash session where 'dc-tools/tools/gv-tui' is the working directory.
    - Done.

Using 'gv_tui':
    - The app is comprised of 4 tabs:
        - Cluster:
            - There will be a short 2-3 seconds of 'nothing' while all data is gathered and parsed.
            - The home tab
            - Shows:
                - 'Health' - looking for 9 ready nodes per rack
                - 'Node GV' - node level Groq validation test status
                - 'Rack GV' - rack level Groq validation test status
                - 'XRK GV' - xrk level Groq validation test status
        - Nodes:
            - Search for node level validation status on a rack basis.
            - Generates a table containing gn1-gn9, validators (tests), and their respective status.
            - When test failures occur, the respective test and node status will display the fault type
              and the accompanying component, ie 'Card_Pcie_Bandwidth_Degraded (C0/R2/N2/C4)'
        - Racks:
            - Search for rack level validation status.
            - Generates a table containing all validators (tests), phases, phase status and phase start time.
        - Cross-racks:
            - Search for cross-rack level validation status.
            - Generates a table containing all validators (tests), phases, phase status and phase start time.

    - All tabs refresh automagically every 60 seconds.
        - People with ADHD can refresh manually by pressing 'r' while viewing any tab.

    - The search bar accepts multiple inputs per tab in a space seperated list
      ie 'c0r1 c0r2 c0r{5..12}' or 'c0r1-c0r2 c0r4-c0r5'.

    - When test failures occur, the respective test and node status will display the fault type
      and the accompanying component, ie 'Card_Pcie_Bandwidth_Degraded (C0/R2/N2/C4)'.

Stand alone scripts:
    - If a terminal user interface isn't really your thing, each of the 'data_*' scripts can
      be run independently.

    - data_cluster.py:
        usage: data_cluster.py [-h] [--format {json,table}] [--racks RACKS [RACKS ...]]

        Display cluster rack health status.

        options:
        -h, --help                  show this help message and exit
        --format {json,table}       Output format: table (default) or json
        --racks RACKS [RACKS ...]   Optional list of specific racks to include (e.g. c0r1 c0r2)

    - data_node.py:
        usage: data_node.py [-h] --racks RACKS [RACKS ...] [--format {json,table}]

        Node validation dashboard CLI

        options:
        -h, --help                  show this help message and exit
        --racks RACKS [RACKS ...]   List of racks (e.g. c0r1, c1r55)
        --format {json,table}       Output format: table (default) or json

    - data_rack.py:
        usage: data_rack.py [-h] --racks RACKS [RACKS ...] [--format {json,table}]

        options:
        -h, --help                show this help message and exit
        --racks RACKS [RACKS ...] List of rack(s) (e.g. c0r1 c0r2)
        --format {json,table}     Output format: table (default) or json

    - data_crossrack.py:
        usage: data_crossrack.py [-h] --racks RACKS [RACKS ...] [--format {json,table}]

        options:
        -h, --help            show this help message and exit
        --racks RACKS [RACKS ...] List of crossrack names (e.g. c0r1-c0r2)
        --format {json,table}     Output format: table (default) or json



Just trying to test things.

Another change?
