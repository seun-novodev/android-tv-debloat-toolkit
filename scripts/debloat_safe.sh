#!/bin/sh
# Safer TCL Android TV Debloat Script

# Disable TCL bloatware (reversible: pm enable --user 0 <package>)
pm disable-user --user 0 com.tcl.browser
pm disable-user --user 0 com.tcl.tv.appstore
pm disable-user --user 0 com.tcl.tv.cast
pm disable-user --user 0 com.tcl.usercenter
pm disable-user --user 0 com.tcl.tclaccount
pm disable-user --user 0 com.tcl.tv.tcloudaccount
pm disable-user --user 0 com.tcl.gallery
pm disable-user --user 0 com.tcl.mediacenter
pm disable-user --user 0 com.tcl.screenadservice
pm disable-user --user 0 com.tcl.screensaver
pm disable-user --user 0 com.tcl.eula

# Disable Google TV Recommendations
pm disable-user --user 0 com.google.android.tvrecommendations

echo "Debloating completed!"
