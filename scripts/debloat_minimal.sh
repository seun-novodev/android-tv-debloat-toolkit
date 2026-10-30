#!/bin/sh
# Disable Google TV Recommendations (only). Undo: pm enable --user 0 <package>

pm disable-user --user 0 com.google.android.tvrecommendations

echo "Recommendations disabled! TV should be faster."
