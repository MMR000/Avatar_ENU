// 🌟 全局状态变量
let audioPlayers = {};

/**
 * 🚀 开始处理文本
 */
async function startProcessing() {
    const text = document.getElementById('text-input').value.trim();
    if (!text) {
        alert('Please enter some text.');
        return;
    }

    const resultsSection = document.getElementById('results');
    resultsSection.innerHTML = '<p class="status-message">⏳ Processing text...</p>';
    const processButton = document.getElementById('process-button');
    processButton.disabled = true;
    processButton.innerText = 'Processing...';

    try {
        // 发送文本到后端进行处理
        const response = await fetch('/process_text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text }),
        });

        const result = await response.json();
        if (result.status === 'success') {
            resultsSection.innerHTML = ''; // 清空结果
            result.stanza_outputs.forEach((output, index) => {
                const audioFile = result.audio_files[index];
                const resultBlock = document.createElement('div');
                resultBlock.classList.add('result-block');
                resultBlock.innerHTML = `
                    <p class="sentence-text">Sentence: ${output.sentence}</p>
                    <p class="classification">Classification: ${output.classification} (Rule ID)</p>
                    <p class="structure">Structure: ${output.structure}</p>
                    <div id="waveform-${index}" class="waveform"></div>
                    <button class="play-button" onclick="togglePlay(${index}, this)">▶️ Play</button>
                    <button class="generate-video" onclick="generateVideo(this, '${audioFile}', ${output.classification})">🎥 Generate Video</button>
                    <div class="loading-spinner" id="spinner-${index}" style="display:none;"></div>
                    <video class="video-player" id="video-player-${index}" controls style="display:none;"></video>
                    <p class="status-message" id="status-${index}"></p>
                `;
                resultsSection.appendChild(resultBlock);

                // 初始化 Wavesurfer
                initializeWaveSurfer(audioFile, `waveform-${index}`);
            });
        } else {
            resultsSection.innerHTML = `<p class="status-message">❌ ${result.message}</p>`;
        }
    } catch (error) {
        console.error('Error processing text:', error);
        resultsSection.innerHTML = `<p class="status-message">❌ An error occurred: ${error.message}</p>`;
    } finally {
        processButton.disabled = false;
        processButton.innerText = '🚀 Start Processing';
    }
}

/**
 * 🎵 初始化 Wavesurfer
 */
function initializeWaveSurfer(audioFile, waveformId) {
    const container = document.getElementById(waveformId);
    audioPlayers[waveformId] = WaveSurfer.create({
        container: container,
        waveColor: '#66d9ff',
        progressColor: '#ff7eb3',
        barWidth: 2,
        responsive: true,
        height: 60,
    });
    audioPlayers[waveformId].load(audioFile);
}

/**
 * 🎧 切换播放状态
 */
function togglePlay(index, button) {
    const waveformId = `waveform-${index}`;
    const player = audioPlayers[waveformId];
    if (player.isPlaying()) {
        player.pause();
        button.innerText = '▶️ Play';
    } else {
        player.play();
        button.innerText = '⏸️ Pause';
    }
}

/**
 * 📹 自动生成视频
 */
async function generateVideo(button, audioFile, classification) {
    button.disabled = true;
    button.innerText = 'Generating...';

    try {
        const response = await fetch('/generate_video', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                audio_file: audioFile,
                classification: classification
            }),
        });

        const result = await response.json();
        console.log('Video Generation Result:', result);

        if (result.status === 'success') {
            // 更新视频播放器的路径
            const resultBlock = button.closest('.result-block');
            const videoPlayer = resultBlock.querySelector('.video-player');
            videoPlayer.src = result.video_url;
            videoPlayer.style.display = 'block';
            videoPlayer.load();
            button.innerText = '🎥 Video Ready';
        } else {
            alert('Video generation failed: ' + result.message);
            button.innerText = 'Generate Video';
        }
    } catch (error) {
        console.error('Error generating video:', error);
        alert('An error occurred while generating the video.');
        button.innerText = 'Generate Video';
    } finally {
        button.disabled = false;
    }
}

/**
 * 🔝 滚动到顶部
 */
function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
}
