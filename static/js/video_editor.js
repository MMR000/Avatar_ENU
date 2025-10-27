let segments = [];

function addSegment() {
    const file = document.getElementById('video-select').value;
    const start = document.getElementById('start-time').value;
    const end = document.getElementById('end-time').value;

    segments.push({ file, start, end });
    console.log(segments);
}

async function previewVideo() {
    const response = await fetch('/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ segments })
    });

    const result = await response.json();
    if (result.status === 'success') {
        document.getElementById('preview-video').src = result.video_url;
        document.getElementById('preview-video').play();
    } else {
        alert('Error: ' + result.message);
    }
}
async function validateVideoLength(selectElement, audioDuration) {
    const videoFile = selectElement.value;
    const response = await fetch('/validate_video', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_file: videoFile, audio_duration: audioDuration })
    });

    const result = await response.json();
    const statusElement = selectElement.nextElementSibling;

    if (result.valid) {
        statusElement.innerHTML = '✅ Video matches audio!';
    } else {
        statusElement.innerHTML = '⚠️ Video too short. Duplicate needed.';
    }
}
async function synthesizeAudio(button, sentence) {
    const response = await fetch('/synthesize_audio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sentence })
    });
    const result = await response.json();
    console.log(result);
}

