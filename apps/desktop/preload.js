const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
    getSources: () => ipcRenderer.invoke('get-sources'),
    startRecording: () => ipcRenderer.invoke('start-recording'),
    stopRecording: (buffer) => ipcRenderer.invoke('stop-recording', buffer),
    onProcessingStatus: (callback) => ipcRenderer.on('processing-status', (_event, value) => callback(value)),
    quitApp: () => ipcRenderer.send('quit-app')
});
