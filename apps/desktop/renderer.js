let mediaRecorder;
let recordedChunks = [];
let isRecording = false;

const startBtn = document.getElementById('recordBtn');
const statusText = document.getElementById('status');
const closeBtn = document.getElementById('closeBtn');

closeBtn.addEventListener('click', () => {
    window.api.quitApp();
});

startBtn.addEventListener('click', async () => {
    if (isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
});

async function startRecording() {
    isRecording = true;
    startBtn.textContent = 'Stop Recording';
    startBtn.classList.add('recording');
    statusText.textContent = 'Recording in progress...';
    statusText.style.color = '#f43f5e';

    try {
        const source = await window.api.getSources();
        const constraints = {
            audio: false,
            video: {
                mandatory: {
                    chromeMediaSource: 'desktop',
                    chromeMediaSourceId: source.id
                }
            }
        };

        const stream = await navigator.mediaDevices.getUserMedia(constraints);
        
        const options = { mimeType: 'video/webm; codecs=vp8' };
        mediaRecorder = new MediaRecorder(stream, options);

        mediaRecorder.ondataavailable = handleDataAvailable;
        mediaRecorder.onstop = handleStop;
        
        await window.api.startRecording();
        mediaRecorder.start(100); // collect 100ms chunks of data

    } catch (e) {
        console.error(e);
        statusText.textContent = 'Failed to start recording';
        statusText.style.color = '#fff';
        resetUI();
    }
}

function handleDataAvailable(e) {
    if (e.data.size > 0) {
        recordedChunks.push(e.data);
    }
}

async function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        statusText.textContent = 'Saving & Processing...';
        statusText.style.color = '#a1a1aa';
    }
}

async function handleStop() {
    const blob = new Blob(recordedChunks, {
        type: 'video/webm; codecs=vp8'
    });
    
    const buffer = await blob.arrayBuffer();
    
    // Clear chunks
    recordedChunks = [];
    resetUI();
    
    // Send to main process
    await window.api.stopRecording(buffer);
}

function resetUI() {
    isRecording = false;
    startBtn.textContent = 'Start Recording';
    startBtn.classList.remove('recording');
}

window.api.onProcessingStatus((status) => {
    statusText.textContent = status;
    if (status.includes('Done') || status.includes('Error')) {
        statusText.style.color = status.includes('Done') ? '#10b981' : '#ef4444';
        setTimeout(() => {
            statusText.textContent = 'Ready to record';
            statusText.style.color = '#a1a1aa';
        }, 5000);
    }
});
