import { writeFileSync, renameSync } from 'node:fs';
const [file,node,runtime,data,base,host]=process.argv.slice(2);
if (![file,node,runtime,data,base].every(value=>typeof value==='string'&&value.startsWith('/'))) throw new Error('Absolute installation paths are required.');
const xml=value=>String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[char]));
const string=value=>`<string>${xml(value)}</string>`;
const settings={PORT:'3847',HOST:'0.0.0.0',DATA_DIR:data};
if(host)settings.KROSHKA_HOSTNAME=`${host}.local`;
const content=`<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key>${string('dev.kroshka.recipes')}
<key>ProgramArguments</key><array>${['/usr/bin/caffeinate','-s',node,'server.js'].map(string).join('')}</array>
<key>WorkingDirectory</key>${string(runtime)}
<key>EnvironmentVariables</key><dict>${Object.entries(settings).map(([key,value])=>`<key>${xml(key)}</key>${string(value)}`).join('')}</dict>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/><key>ThrottleInterval</key><integer>15</integer>
<key>StandardOutPath</key>${string(`${base}/logs/server.log`)}
<key>StandardErrorPath</key>${string(`${base}/logs/server-error.log`)}
</dict></plist>\n`;
writeFileSync(file+'.new',content,{mode:0o600});renameSync(file+'.new',file);
