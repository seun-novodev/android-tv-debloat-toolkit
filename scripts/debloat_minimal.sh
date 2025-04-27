#!/bin/sh
# Remove Google TV Recommendations (only)

pm uninstall --user 0 com.google.android.tvrecommendations

echo "Recommendations removed! TV should be faster."
