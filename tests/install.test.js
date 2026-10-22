import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,rmSync,writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {execFileSync} from 'node:child_process';

test('Mac launch configuration preserves spaces, Cyrillic and XML characters, including during updates',()=>{
 const dir=mkdtempSync(join(tmpdir(),'kroshka-installer-'));
 try {
  const file=join(dir,'agent.plist');
  const base=join(dir,'Семейная кухня & рецепты');
  const args=['mac/write-launch-agent.js',file,'/opt/homebrew/bin/node',`${base}/app`,`${base}/data`,base,'Family-Mac'];
  execFileSync(process.execPath,args);
  const parsed=JSON.parse(execFileSync('python3',['-c','import plistlib,json,sys; print(json.dumps(plistlib.load(open(sys.argv[1],"rb"))))',file],{encoding:'utf8'}));
  assert.deepEqual(parsed.ProgramArguments,['/usr/bin/caffeinate','-s','/opt/homebrew/bin/node','server.js']);
  assert.equal(parsed.EnvironmentVariables.DATA_DIR,`${base}/data`);
  assert.equal(parsed.EnvironmentVariables.KROSHKA_HOSTNAME,'Family-Mac.local');
  assert.equal(parsed.EnvironmentVariables.PORT,'3847');
  assert.equal(parsed.WorkingDirectory,`${base}/app`);
  assert.equal(parsed.RunAtLoad,true);assert.equal(parsed.KeepAlive,true);
  assert.equal(parsed.StandardOutPath,`${base}/logs/server.log`);
  writeFileSync(join(dir,'recipes-preservation-check'),'keep my recipes');
  execFileSync(process.execPath,args);
  assert.equal(readFileSync(join(dir,'recipes-preservation-check'),'utf8'),'keep my recipes');
  assert.equal(readFileSync(file,'utf8').includes('Кухня & рецепты'),false);
 } finally {rmSync(dir,{recursive:true,force:true});}
});

test('Mac installer has valid shell syntax and preserves persistent storage',()=>{
 execFileSync('bash',['-n','Установить Крошку.command']);
 execFileSync('sh',['-n','mac/Kroshka']);
 const installer=readFileSync('Установить Крошку.command','utf8');
 assert.ok(installer.includes('TASK_DATA_DIR="$TASK_BASE_DIR/data"'));
 assert.ok(!installer.includes('rm -rf "$TASK_DATA_DIR"'));
 assert.ok(installer.includes('launchctl bootstrap'));
 const info=JSON.parse(execFileSync('python3',['-c','import plistlib,json; print(json.dumps(plistlib.load(open("mac/Info.plist","rb"))))'],{encoding:'utf8'}));
 assert.equal(info.CFBundleExecutable,'Kroshka');
 assert.equal(info.CFBundleIdentifier,'dev.kroshka.launcher');
});
