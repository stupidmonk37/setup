#!/usr/bin/env zsh

set -e

echo "🔧 Setting up your Mac..."
# ===================================================================
# =====[ Xcode CLI Tools ]===========================================
# ===================================================================
if ! xcode-select -p &>/dev/null; then
    echo "📦 Installing Xcode Command Line Tools..."
    xcode-select --install
    until xcode-select -p &>/dev/null; do sleep 5; done
fi

# ===================================================================
# =====[ macos preferences ]=========================================
# ===================================================================
echo "⚙️ Configuring macOS settings..."

# Disable warning when changing a file extension
defaults write com.apple.finder FXEnableExtensionChangeWarning -bool false

# Avoid creating .DS_Store files on network/USB volumes
defaults write com.apple.desktopservices DSDontWriteNetworkStores -bool true
defaults write com.apple.desktopservices DSDontWriteUSBStores -bool true

# Keep folders on top when sorting by name
defaults write com.apple.finder _FXSortFoldersFirst -bool true

# Show status bar
defaults write com.apple.finder ShowStatusBar -bool true

# Disable auto-correct system-wide
defaults write NSGlobalDomain NSAutomaticSpellingCorrectionEnabled -bool false

# Disable system-wide resume (reopen windows on login)
defaults write com.apple.systempreferences NSQuitAlwaysKeepsWindows -bool false

# Disable notification center
launchctl unload -w /System/Library/LaunchAgents/com.apple.notificationcenterui.plist 2>/dev/null

# Include date in screenshot filename
defaults write com.apple.screencapture "name" "Screenshot"

# Disable shadow in screenshots
defaults write com.apple.screencapture disable-shadow -bool true

# Disable auto-capitalization
defaults write NSGlobalDomain NSAutomaticCapitalizationEnabled -bool false

# Disable smart dashes (good for coders)
defaults write NSGlobalDomain NSAutomaticDashSubstitutionEnabled -bool false

# Disable smart quotes (good for coders)
defaults write NSGlobalDomain NSAutomaticQuoteSubstitutionEnabled -bool false

# Show Xcode build duration
defaults write com.apple.dt.Xcode ShowBuildOperationDuration -bool true

osascript -e 'tell application "Finder" to set desktop picture to POSIX file "/Library/Desktop Pictures/Mojave Day.jpg"'

# Disable crash reporter
defaults write com.apple.CrashReporter DialogType none

# Speed up animations when opening folders in Launchpad
defaults write com.apple.dock springboard-show-duration -int 0
defaults write com.apple.dock springboard-hide-duration -int 0

# Disable AutoFill in Safari
defaults write com.apple.Safari AutoFillFromAddressBook -bool false
defaults write com.apple.Safari AutoFillPasswords -bool false
defaults write com.apple.Safari AutoFillCreditCardData -bool false

# Set a custom login message
sudo defaults write /Library/Preferences/com.apple.loginwindow LoginwindowText "👋 Welcome to your Mac!"

# Disable the startup chime (Intel Macs)
sudo nvram SystemAudioVolume=" "

# Disable dashboard (on old systems)
defaults write com.apple.dashboard mcx-disabled -bool true

# Expand save panel by default
defaults write NSGlobalDomain NSNavPanelExpandedStateForSaveMode -bool true

# Require password immediately after sleep
defaults write com.apple.screensaver askForPassword -int 1
defaults write com.apple.screensaver askForPasswordDelay -int 0

# Show Library folder
chflags nohidden ~/Library

# Show full POSIX path in Finder title
defaults write com.apple.finder _FXShowPosixPathInTitle -bool true

# Disable indexing on external volumes
sudo mdutil -i off /Volumes/ExternalDriveName

# Rebuild index
sudo mdutil -E /

# Disable captive portal pop-up (useful on developer machines)
sudo defaults write /Library/Preferences/SystemConfiguration/com.apple.captive.control Active -bool false

# Enable AirDrop over Ethernet
defaults write com.apple.NetworkBrowser BrowseAllInterfaces -bool true

# Tap to click
defaults write com.apple.AppleMultitouchTrackpad Clicking -bool true

# Tracking speed (1–5 for mouse, 0–3 for trackpad)
defaults write -g com.apple.trackpad.scaling -float 2.5
defaults write -g com.apple.mouse.scaling -float 3.0

# Never sleep while on charger
sudo pmset -c sleep 0

# Sleep after 10 mins on battery
sudo pmset -b sleep 10

# Prevent disk sleep
sudo pmset -a disksleep 0

# Save to disk by default, not iCloud
defaults write NSGlobalDomain NSDocumentSaveNewDocumentsToCloud -bool false

# Speed up window resize animations
defaults write NSGlobalDomain NSWindowResizeTime -float 0.001

# Disable opening/closing window animations
defaults write NSGlobalDomain NSAutomaticWindowAnimationsEnabled -bool false

# Expand print panel by default
defaults write NSGlobalDomain PMPrintingExpandedStateForPrint -bool true
defaults write NSGlobalDomain PMPrintingExpandedStateForPrint2 -bool true

# Disable window restore for all apps (system resume)
defaults write com.apple.systempreferences NSQuitAlwaysKeepsWindows -bool false

# Disable Dashboard (for older macOS versions)
defaults write com.apple.dashboard mcx-disabled -bool true

# Don't group windows by app in Mission Control
defaults write com.apple.dock expose-group-by-app -bool false

# Disable auto-correct globally
defaults write NSGlobalDomain NSAutomaticSpellingCorrectionEnabled -bool false

# Disable emoji substitution
defaults write NSGlobalDomain NSAutomaticTextReplacementEnabled -bool false

# Disable press-and-hold for special keys (use key repeat instead)
defaults write -g ApplePressAndHoldEnabled -bool false

# Don’t show recent apps in Dock
defaults write com.apple.dock show-recents -bool false

# Hide user list at login screen
sudo defaults write /Library/Preferences/com.apple.loginwindow Hide500Users -bool true
sudo defaults write /Library/Preferences/com.apple.loginwindow SHOWFULLNAME -bool true

# Use 24-hour time
defaults write NSGlobalDomain AppleICUForce24HourTime -bool true

# Disable natural language date parsing in Calendar
defaults write com.apple.iCal IncludeDebugMenu -bool true

# Mute system boot chime (Intel Macs)
sudo nvram SystemAudioVolume=" "

# Set alert volume to low
defaults write NSGlobalDomain com.apple.sound.beep.volume -float 0.1

# Enable AirDrop over all interfaces
defaults write com.apple.NetworkBrowser BrowseAllInterfaces -bool true

# Disable Captive Portal popups
sudo defaults write /Library/Preferences/SystemConfiguration/com.apple.captive.control Active -bool false

# Enable Safari’s debug menu
defaults write com.apple.Safari IncludeInternalDebugMenu -bool true

# Enable full URL in Safari address bar
defaults write com.apple.Safari ShowFullURLInSmartSearchField -bool true

# Disable Safari thumbnail caching (for privacy)
defaults write com.apple.Safari DebugSnapshotsUpdatePolicy -int 2

# Show item info near icons on desktop
defaults write com.apple.finder ShowItemInfo -bool true

# Snap-to-grid for desktop icons
/usr/libexec/PlistBuddy -c "Set :DesktopViewSettings:IconViewSettings:arrangeBy grid" ~/Library/Preferences/com.apple.finder.plist

# Enable HiDPI display modes (for Retina screen simulation)
sudo defaults write /Library/Preferences/com.apple.windowserver DisplayResolutionEnabled -bool true

# Disable automatic rearrangement of menu bar icons (macOS Ventura+)
defaults write com.apple.controlcenter.plist AutoOrder -bool false

# Prevent system sleep entirely
sudo systemsetup -setcomputersleep Never

# Auto-disable Wi-Fi when Ethernet is connected (via network service order)
networksetup -listnetworkserviceorder
# (Then reorder to prioritize Ethernet)

# Disable Notification Center (only works on older macOS versions)
launchctl unload -w /System/Library/LaunchAgents/com.apple.notificationcenterui.plist 2>/dev/null

# Check for software updates daily instead of weekly:
defaults write com.apple.SoftwareUpdate ScheduleFrequency -int 1

# 	•	Disable window animations and Get Info animations:
defaults write com.apple.finder DisableAllAnimations -bool true

#	•	Automatically open a new Finder window when a volume is mounted:
defaults write com.apple.frameworks.diskimages auto-open-ro-root -bool true
defaults write com.apple.frameworks.diskimages auto-open-rw-root -bool true
defaults write com.apple.finder OpenWindowForNewRemovableDisk -bool true

# Use list view in all Finder windows by default:
defaults write com.apple.finder FXPreferredViewStyle -string "Nlsv"

#  	•	Expand the following File Info panes: “General”, “Open with”, and “Sharing & Permissions”:
defaults write com.apple.finder FXInfoPanesExpanded -dict \
  General -bool true \
  OpenWith -bool true \
  Privileges -bool true

#	•	Don’t send search queries to Apple:
defaults write com.apple.Safari UniversalSearchEnabled -bool false
defaults write com.apple.Safari SuppressSearchSuggestions -bool true

# 	•	Set Safari’s home page to about:blank for faster loading:
defaults write com.apple.Safari HomePage -string "about:blank"

# 	•	Reduce window animation duration system-wide (snappier UX):
defaults write NSGlobalDomain NSWindowResizeTime -float 0.001

#	•	Speed up Dock auto-hide/show time:
defaults write com.apple.dock autohide-delay -float 0
defaults write com.apple.dock autohide-time-modifier -float 0.15 && killall Dock
# 	•	Reduce transparency (increase contrast):
defaults write com.apple.universalaccess reduceTransparency -bool true

# 	•	Disable confirmation when opening downloaded apps (Gatekeeper prompt):
defaults write com.apple.LaunchServices LSQuarantine -bool false

# 	•	Disable line marks (those annoying colored bars on the left):
defaults write com.apple.Terminal ShowLineMarks -int 0

# 	•	Set Pro theme as default (you can change this to any theme you like):
defaults write com.apple.terminal "Default Window Settings" -string "Pro"
defaults write com.apple.terminal "Startup Window Settings" -string "Pro"

# ===================================================================
# =====[ Menubar ]===================================================
# ===================================================================
# Set specific icons to appear:
defaults write com.apple.systemuiserver menuExtras -array \
  "/System/Library/CoreServices/Menu Extras/Clock.menu" \
  "/System/Library/CoreServices/Menu Extras/Bluetooth.menu" \
  "/System/Library/CoreServices/Menu Extras/AirPort.menu" \
  "/System/Library/CoreServices/Menu Extras/Battery.menu"
killall SystemUIServer

# Enable auto-hide:
defaults write NSGlobalDomain _HIHideMenuBar -bool true
killall SystemUIServer

# Example: Remove Time Machine from the menu bar
defaults write com.apple.systemuiserver "NSStatusItem Visible com.apple.menuextra.TimeMachine" -bool false && killall SystemUIServer

# Example: Hide Siri icon
defaults write com.apple.Siri StatusMenuVisible -bool false && killall SystemUIServer

# Example: Hide User Switching icon
defaults write com.apple.systemuiserver "NSStatusItem Visible com.apple.menuextra.user" -bool false && killall SystemUIServer

# ===================================================================
# =====[ UI Tweeks ]=================================================
# ===================================================================
defaults write NSGlobalDomain NSWindowResizeTime -float 0.001
defaults write NSGlobalDomain NSAutomaticWindowAnimationsEnabled -bool false
defaults write NSGlobalDomain AppleShowAllExtensions -bool true
defaults write NSGlobalDomain NSDocumentSaveNewDocumentsToCloud -bool false

# Toggle dark/light appearance:
osascript -e 'tell app "System Events" to tell appearance preferences to set dark mode to not dark mode'

# Always show scrollbars
defaults write NSGlobalDomain AppleShowScrollBars -string "Always"

# ===================================================================
# =====[ Keyboard and typing ]=======================================
# ===================================================================
defaults write NSGlobalDomain ApplePressAndHoldEnabled -bool false
defaults write NSGlobalDomain KeyRepeat -int 1
defaults write NSGlobalDomain InitialKeyRepeat -int 15
defaults write NSGlobalDomain NSAutomaticSpellingCorrectionEnabled -bool false
defaults write NSGlobalDomain NSAutomaticQuoteSubstitutionEnabled -bool false
defaults write NSGlobalDomain NSAutomaticDashSubstitutionEnabled -bool false

# Fast key repeat rate (feels much more responsive):
defaults write NSGlobalDomain KeyRepeat -int 1
defaults write NSGlobalDomain InitialKeyRepeat -int 10

# ===================================================================
# =====[ Finder Settings ]===========================================
# ===================================================================
defaults write com.apple.finder AppleShowAllFiles -bool true
defaults write com.apple.finder ShowPathbar -bool true
defaults write com.apple.finder FXPreferredViewStyle -string "Nlsv"
defaults write com.apple.finder _FXShowPosixPathInTitle -bool true
chflags nohidden ~/Library

# Show hidden files by default:
defaults write com.apple.finder AppleShowAllFiles -bool true && killall Finder

# Disable warning when changing a file extension:
defaults write com.apple.finder FXEnableExtensionChangeWarning -bool false && killall Finder

# Use list view in all Finder windows by default:
defaults write com.apple.finder FXPreferredViewStyle -string "Nlsv"
Other options:
"icnv" = Icon view
"clmv" = Column view
"Flwv" = Gallery (Cover Flow) view

# Show ~/Library and /Volumes in sidebar:
sudo chflags nohidden /Volumes

# Automatically open a Finder window when a volume is mounted:
defaults write com.apple.frameworks.diskimages auto-open-ro-root -bool true
defaults write com.apple.frameworks.diskimages auto-open-rw-root -bool true
defaults write com.apple.finder OpenWindowForNewRemovableDisk -bool true

# Set default Finder window to open your home directory:
defaults write com.apple.finder NewWindowTarget -string "PfLo"
defaults write com.apple.finder NewWindowTargetPath -string "file://${HOME}/"

# Show all file extensions:
defaults write NSGlobalDomain AppleShowAllExtensions -bool true

# ===================================================================
# =====[ Dock and Mission Control ]==================================
# ===================================================================
defaults write com.apple.dock autohide -bool true
defaults write com.apple.dock tilesize -int 36
defaults write com.apple.dock minimize-to-application -bool true
defaults write com.apple.dock mru-spaces -bool false

# ===================================================================
# =====[ Screenshots ]===============================================
# ===================================================================
mkdir -p "$HOME/Screenshots"
defaults write com.apple.screencapture location -string "$HOME/Screenshots"
defaults write com.apple.screencapture type -string "png"

# ===================================================================
# =====[ Trackpad and Mouse ]========================================
# ===================================================================
defaults write com.apple.AppleMultitouchTrackpad Clicking -bool true
defaults write -g com.apple.trackpad.scaling -float 2.5
defaults write -g com.apple.mouse.scaling -float 3.0
# Disable “natural” (Lion-style) scrolling:
defaults write NSGlobalDomain com.apple.swipescrolldirection -bool false

# ===================================================================
# =====[ Terminal ]==================================================
# ===================================================================
defaults write com.apple.terminal StringEncodings -array 4
defaults write com.googlecode.iterm2 PromptOnQuit -bool false

# ===================================================================
# =====[ Power management ]==========================================
# ===================================================================
sudo pmset -c sleep 0
sudo pmset -b sleep 10
sudo pmset -a disksleep 0

# ===================================================================
# =====[ Spotlight ]=================================================
# ===================================================================
sudo mdutil -i off /Volumes/ExternalDriveName
sudo mdutil -E 

# ===================================================================
# =====[ Network and Sharing ]=======================================
# ===================================================================
sudo defaults write /Library/Preferences/SystemConfiguration/com.apple.captive.control Active -bool false
defaults write com.apple.NetworkBrowser BrowseAllInterfaces -bool true

# ===================================================================
# =====[ Security and Privacy ]======================================
# ===================================================================
defaults write com.apple.screensaver askForPassword -int 1
defaults write com.apple.screensaver askForPasswordDelay -int 0

# ===================================================================
# =====[ Safari ]====================================================
# ===================================================================
defaults write com.apple.Safari IncludeDevelopMenu -bool true
defaults write com.apple.Safari AutoOpenSafeDownloads -bool false

# ===================================================================
# =====[ cleanup ]===================================================
# ===================================================================
killall Finder 2>/dev/null || true
killall Dock 2>/dev/null || true

# ===================================================================
# =====[ UI ]========================================================
# ===================================================================
defaults write NSGlobalDomain AppleShowAllExtensions -bool true
defaults write com.apple.finder AppleShowAllFiles -bool true
defaults write com.apple.finder ShowPathbar -bool true
defaults write com.apple.dock autohide -bool true
defaults write com.apple.dock tilesize -int 36
defaults write com.apple.screencapture location -string "$HOME"
defaults write com.apple.screencapture type -string "png"
defaults write com.apple.LaunchServices LSQuarantine -bool false

# ===================================================================
# =====[ keyboard ]==================================================
# ===================================================================
defaults write NSGlobalDomain ApplePressAndHoldEnabled -bool false
defaults write NSGlobalDomain KeyRepeat -int 1
defaults write NSGlobalDomain InitialKeyRepeat -int 15

### 4. Mac App Store (MAS)
if ! command -v mas &>/dev/null; then
    echo "💻 Installing mas (Mac App Store CLI)..."
    brew install mas
fi

echo "🛍 Installing Mac App Store apps..."
mas install 497799835  # Xcode
# Add more MAS IDs as needed

echo "✅ Setup complete! Restart your Mac for all changes to take full effect."

#xcode-select --install

#echo "Complete the installation of Xcode Command Line Tools before proceeding."
#echo "Press enter to continue..."
#read

#mkdir "${HOME}/Desktop/Screenshots"
#defaults write com.apple.screencapture location "${HOME}/Desktop/Screenshots"
#killall SystemUIServer

# Get the absolute path to the image
IMAGE_PATH="${HOME}/dotfiles/settings/Desktop.png"

