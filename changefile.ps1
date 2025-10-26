# === Pad naar je add-on config ===
$cfg = "jura_s8_price_addon\config.yaml"

# === 1. Controleer of bestand bestaat ===
if (-Not (Test-Path $cfg)) {
    Write-Host "❌ Kan $cfg niet vinden. Voer dit uit in de repo-root."
    exit
}

# === 2. Backup maken ===
Copy-Item $cfg "$cfg.bak" -Force
Write-Host "🧩 Backup aangemaakt: $cfg.bak"

# === 3. Verwijder headers-secties uit sites ===
(Get-Content $cfg) |
Where-Object {$_ -notmatch '^\s*headers'} |
Set-Content $cfg -Encoding UTF8

# === 4. Fix schema: int(30, 86400) → int(30,86400)
(gc $cfg) -replace 'int\(30, 86400\)', 'int(30,86400)' |
    Set-Content $cfg -Encoding UTF8

# === 5. Vervang schema: mqtt_port type int → port
(gc $cfg) -replace 'mqtt_port: int', 'mqtt_port: port' |
    Set-Content $cfg -Encoding UTF8

Write-Host "✅ config.yaml aangepast voor HA-schema-validatie."

# === 6. Git commit en push ===
git add $cfg
git commit -m "fix(add-on): HA schema compat – verwijder headers en fix int(30,86400) #patch"
git push origin main
