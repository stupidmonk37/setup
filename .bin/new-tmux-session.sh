#! /bin/bash

# values should be in space-separated lists:
# tmux-sessions.sh c5r1 c5r2 c5r3 c5r4

LIST=$@

for i in $LIST; do 
    tmux new-session -d -s "$i" -n "$i"
    echo "✅ Created session: $i"
done
