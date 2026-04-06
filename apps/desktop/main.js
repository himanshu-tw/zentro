const { app, BrowserWindow, ipcMain, desktopCapturer, screen } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const { uIOhook, UiohookKey } = require('uiohook-napi');

let mainWindow;
let isRecording = false;
let recordStartTime = 0;
let mouseEvents = [];
let lastMouseMoveTime = 0;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 320,
    height: 180,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    },
    alwaysOnTop: true,
    transparent: true,
    frame: false,
    resizable: false,
    x: screen.getPrimaryDisplay().workAreaSize.width - 340,
    y: screen.getPrimaryDisplay().workAreaSize.height - 200
  });

  mainWindow.loadFile('index.html');
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });

  // Start global hook
  uIOhook.start();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    uIOhook.stop();
    app.quit();
  }
});

app.on('before-quit', () => {
  uIOhook.stop();
});

// Setup hook listeners
uIOhook.on('mousemove', (e) => {
  if (!isRecording) return;
  const now = Date.now();
  if (now - lastMouseMoveTime > 50) { // Throttle slightly
    mouseEvents.push({
      type: 'move',
      x: e.x,
      y: e.y,
      t: now - recordStartTime
    });
    lastMouseMoveTime = now;
  }
});

uIOhook.on('mousedown', (e) => {
  if (!isRecording) return;
  mouseEvents.push({
    type: 'click',
    x: e.x,
    y: e.y,
    t: Date.now() - recordStartTime
  });
});

// IPC handlers
ipcMain.handle('get-sources', async () => {
  const sources = await desktopCapturer.getSources({ types: ['screen'] });
  return sources[0]; // Get the primary screen
});

ipcMain.handle('start-recording', () => {
  isRecording = true;
  mouseEvents = [];
  recordStartTime = Date.now();
  console.log('Started recording');
});

ipcMain.handle('stop-recording', async (event, videoBuffer) => {
  isRecording = false;
  console.log('Stopped recording, saving files...');
  
  const outputDir = path.join(app.getPath('userData'), 'recordings');
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const timestamp = Date.now();
  const videoPath = path.join(outputDir, `recording_${timestamp}.webm`);
  const jsonPath = path.join(outputDir, `mouse_events_${timestamp}.json`);
  const finalPath = path.join(outputDir, `output_${timestamp}.mp4`);

  fs.writeFileSync(jsonPath, JSON.stringify(mouseEvents, null, 2));
  fs.writeFileSync(videoPath, Buffer.from(videoBuffer));

  console.log('Files saved to', outputDir);

  // Trigger Python Processing
  const processorPath = path.join(__dirname, '..', '..', 'packages', 'processor', 'process.py');
  const pythonExecutable = path.join(__dirname, '..', '..', 'packages', 'processor', 'venv', 'bin', 'python3');
  
  if (fs.existsSync(pythonExecutable)) {
    console.log('Starting Python processor...');
    event.sender.send('processing-status', 'Processing video...');
    
    // Pass args: <script> <video_in> <json_in> <video_out>
    const processChild = spawn(pythonExecutable, [processorPath, videoPath, jsonPath, finalPath]);
    
    processChild.stdout.on('data', (data) => {
      console.log(`Python stdout: ${data}`);
    });
    
    processChild.stderr.on('data', (data) => {
      console.error(`Python stderr: ${data}`);
    });
    
    processChild.on('close', (code) => {
      console.log(`Python process exited with code ${code}`);
      if (code === 0) {
        event.sender.send('processing-status', `Done! Saved as output_${timestamp}.mp4`);
      } else {
        event.sender.send('processing-status', `Error processing video (code ${code}).`);
      }
    });
  } else {
    console.error('Python environment not found. Did you run npm run setup:python?');
    event.sender.send('processing-status', 'Error: Python venv not found.');
  }

  return { videoPath, jsonPath, finalPath };
});

ipcMain.on('quit-app', () => {
    app.quit();
});
