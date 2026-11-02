#!/usr/bin/env bash
set -euo pipefail
set +x
keychain="$RUNNER_TEMP/clash-party.keychain-db"
case "${1:-}" in
  import)
    for name in CSC_LINK CSC_KEY_PASSWORD CSC_INSTALLER_LINK CSC_INSTALLER_KEY_PASSWORD APPLE_ID APPLE_APP_SPECIFIC_PASSWORD APPLE_TEAM_ID; do
      if [[ -z "${!name:-}" ]]; then
        echo "Missing macOS signing Secret: $name" >&2
        exit 1
      fi
    done
    password="$(openssl rand -hex 24)"
    security create-keychain -p "$password" "$keychain"
    security set-keychain-settings -lut 21600 "$keychain"
    security unlock-keychain -p "$password" "$keychain"
    certificate="$RUNNER_TEMP/clash-party-certificate.p12"
    trap 'rm -f "$certificate"' EXIT
    for kind in application installer; do
      if [[ "$kind" == application ]]; then data="$CSC_LINK"; pass="$CSC_KEY_PASSWORD";
      else data="$CSC_INSTALLER_LINK"; pass="$CSC_INSTALLER_KEY_PASSWORD"; fi
      printf '%s' "$data" | base64 --decode > "$certificate"
      security import "$certificate" -k "$keychain" -P "$pass" -A -T /usr/bin/codesign -T /usr/bin/security -T /usr/bin/productsign
      rm -f "$certificate"
    done
    security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$password" "$keychain" >/dev/null 2>&1
    security list-keychains -d user -s "$keychain" $(security list-keychains -d user | tr -d '"')
    security default-keychain -s "$keychain"
    application="$(security find-identity -v -p codesigning "$keychain" | awk -F'"' '/Developer ID Application/ { print $2; exit }')"
    [[ -n "$application" ]] || { echo 'No Developer ID Application identity' >&2; exit 1; }
    {
      echo "CSC_KEYCHAIN=$keychain"
      echo "CSC_NAME=${application#Developer ID Application: }"
      echo 'CSC_IDENTITY_AUTO_DISCOVERY=true'
    } >> "$GITHUB_ENV"
    ;;
  sign)
    installer="$(security find-identity -v "$keychain" | awk -F'"' '/Developer ID Installer/ { print $2; exit }')"
    [[ -n "$installer" ]] || { echo 'No Developer ID Installer identity' >&2; exit 1; }
    shopt -s nullglob
    packages=(source/dist/*.pkg)
    [[ ${#packages[@]} -eq 1 ]] || { echo 'Expected one installer package' >&2; exit 1; }
    pkg="${packages[0]}"
    unsigned="$RUNNER_TEMP/clash-party-unsigned.pkg"
    mv "$pkg" "$unsigned"
    productsign --keychain "$keychain" --sign "$installer" "$unsigned" "$pkg"
    rm -f "$unsigned"
    xcrun notarytool submit "$pkg" --apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" --password "$APPLE_APP_SPECIFIC_PASSWORD" --wait
    xcrun stapler staple "$pkg"
    ;;
  cleanup)
    if [[ -f "$keychain" ]]; then security delete-keychain "$keychain"; fi
    ;;
  *) echo 'Usage: sign-macos.sh import|sign|cleanup' >&2; exit 1 ;;
esac
