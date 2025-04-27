#!/bin/sh
# Safer TCL Android TV Debloat Script

# Remove TCL bloatware
pm uninstall --user 0 com.tcl.browser
pm uninstall --user 0 com.tcl.tv.appstore
pm uninstall --user 0 com.tcl.tv.cast
pm uninstall --user 0 com.tcl.usercenter
pm uninstall --user 0 com.tcl.tclaccount
pm uninstall --user 0 com.tcl.tv.tcloudaccount
pm uninstall --user 0 com.tcl.gallery
pm uninstall --user 0 com.tcl.mediacenter
pm uninstall --user 0 com.tcl.screenadservice
pm uninstall --user 0 com.tcl.screensaver
pm uninstall --user 0 com.tcl.eula

# Remove Google TV Recommendations
pm uninstall --user 0 com.google.android.tvrecommendations

echo "Debloating completed!"
