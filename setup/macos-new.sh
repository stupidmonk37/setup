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
# =====[ macOS Preferences ]=========================================
# ===================================================================
echo "⚙️ Configuring macOS settings..."

# Finder and Desktop
defaults write com.apple.finder FXEnableExtensionChangeWarning -bool false
defaults write com.apple.desktopservices DSDontWriteNetworkStores -bool true
defaults write com.apple.desktopservices DSDontWriteUSBStores -bool true
defaults write com.apple.finder _FXSortFoldersFirst -bool true
defaults write com.apple.finder ShowStatusBar -bool true
defaults write com.apple.finder _FXShowPosixPathInTitle -bool true
defaults write com.apple.finder FXPreferredViewStyle -string "Nlsv"
defaults write com.apple.finder ShowItemInfo -bool true
/usr/libexec/PlistBuddy -c "Set :DesktopViewSettings:IconViewSettings:arrangeBy grid" ~/Library/Preferences/com.apple.finder.plist
chflags nohidden ~/Library
sudo chflags nohidden /Volumes

# Global System Preferences
defaults write NSGlobalDomain NSAutomaticSpellingCorrectionEnabled -bool false
defaults write NSGlobalDomain NSAutomaticCapitalizationEnabled -bool false
defaults write NSGlobalDomain NSAutomaticDashSubstitutionEnabled -bool false
defaults write NSGlobalDomain NSAutomaticQuoteSubstitutionEnabled -bool false
defaults write NSGlobalDomain NSAutomaticWindowAnimationsEnabled -bool false
defaults write NSGlobalDomain NSDocumentSaveNewDocumentsToCloud -bool false
defaults write NSGlobalDomain NSWindowResizeTime -float 0.001
defaults write NSGlobalDomain AppleShowAllExtensions -bool true
defaults write NSGlobalDomain AppleShowScrollBars -string "Always"
defaults write NSGlobalDomain ApplePressAndHoldEnabled -bool false
defaults write NSGlobalDomain KeyRepeat -int 1
defaults write NSGlobalDomain InitialKeyRepeat -int 10
defaults write NSGlobalDomain AppleICUForce24HourTime -bool true
defaults write NSGlobalDomain com.apple.sound.beep.volume -float 0.1

# Screenshots
defaults write com.apple.screencapture "name" "Screenshot"
defaults write com.apple.screencapture disable-shadow -bool true

# Resume behavior
defaults write com.apple.systempreferences NSQuitAlwaysKeepsWindows -bool false

# Notification Center
launchctl unload -w /System/Library/LaunchAgents/com.apple.notificationcenterui.plist 2>/dev/null

# Xcode
defaults write com.apple.dt.Xcode ShowBuildOperationDuration -bool true

# Login and boot
sudo defaults write /Library/Preferences/com.apple.loginwindow LoginwindowText "👋 Welcome to your Mac!"
sudo nvram SystemAudioVolume=" "
sudo defaults write /Library/Preferences/com.apple.loginwindow Hide500Users -bool true
sudo defaults write /Library/Preferences/com.apple.loginwindow SHOWFULLNAME -bool true

# Safari
defaults write com.apple.Safari AutoFillFromAddressBook -bool false
defaults write com.apple.Safari AutoFillPasswords -bool false
defaults write com.apple.Safari AutoFillCreditCardData -bool false
defaults write com.apple.Safari IncludeInternalDebugMenu -bool true
defaults write com.apple.Safari ShowFullURLInSmartSearchField -bool true
defaults write com.apple.Safari DebugSnapshotsUpdatePolicy -int 2
defaults write com.apple.Safari UniversalSearchEnabled -bool false
defaults write com.apple.Safari SuppressSearchSuggestions -bool true
defaults write com.apple.Safari HomePage -string "about:blank"

# Dock and Mission Control
defaults write com.apple.dock springboard-show-duration -int 0
defaults write com.apple.dock springboard-hide-duration -int 0
defaults write com.apple.dock expose-group-by-app -bool false
defaults write com.apple.dock show-recents -bool false
defaults write com.apple.dock autohide -bool true
defaults write com.apple.dock tilesize -int 36
defaults write com.apple.dock minimize-to-application -bool true
defaults write com.apple.dock autohide-delay -float 0
defaults write com.apple.dock autohide-time-modifier -float 0.15 && killall Dock

# Energy and sleep
sudo pmset -c sleep 0
sudo pmset -b sleep 10
sudo pmset -a disksleep 0
sudo systemsetup -setcomputersleep Never

# Captive Portal
sudo defaults write /Library/Preferences/SystemConfiguration/com.apple.captive.control Active -bool false

# Network
defaults write com.apple.NetworkBrowser BrowseAllInterfaces -bool true
networksetup -listnetworkserviceorder

# Terminal
defaults write com.apple.Terminal ShowLineMarks -int 0
defaults write com.apple.terminal "Default Window Settings" -string "Pro"
defaults write com.apple.terminal "Startup Window Settings" -string "Pro"

# Calendar
defaults write com.apple.iCal IncludeDebugMenu -bool true

# Appearance
osascript -e 'tell app "System Events" to tell appearance preferences to set dark mode to not dark mode'
defaults write com.apple.universalaccess reduceTransparency -bool true

# Menubar
defaults write com.apple.systemuiserver menuExtras -array \
  "/System/Library/CoreServices/Menu Extras/Clock.menu" \
  "/System/Library/CoreServices/Menu Extras/Bluetooth.menu" \
  "/System/Library/CoreServices/Menu Extras/AirPort.menu" \
  "/System/Library/CoreServices/Menu Extras/Battery.menu"
killall SystemUIServer
defaults write NSGlobalDomain _HIHideMenuBar -bool true && killall SystemUIServer
defaults write com.apple.systemuiserver "NSStatusItem Visible com.apple.menuextra.TimeMachine" -bool false && killall SystemUIServer
defaults write com.apple.Siri StatusMenuVisible -bool false && killall SystemUIServer
defaults write com.apple.systemuiserver "NSStatusItem Visible com.apple.menuextra.user" -bool false && killall SystemUIServer

# Software update
defaults write com.apple.SoftwareUpdate ScheduleFrequency -int 1

# Finder enhancements
defaults write com.apple.frameworks.diskimages auto-open-ro-root -bool true
defaults write com.apple.frameworks.diskimages auto-open-rw-root -bool true
defaults write com.apple.finder OpenWindowForNewRemovableDisk -bool true
defaults write com.apple.finder NewWindowTarget -string "PfLo"
defaults write com.apple.finder NewWindowTargetPath -string "file://${HOME}/"
