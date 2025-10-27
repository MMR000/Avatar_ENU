async function synthesizeAudio(button, sentence) {
    const statusMessage = button.nextElementSibling.nextElementSibling;
    const audioPlayer = button.nextElementSibling;

    statusMessage.innerText = "⏳ Generating audio...";
    button.disabled = true;

    try {
        const response = await fetch('/synthesize_audio', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sentence: sentence })
        });

        const result = await response.json();

        if (result.status === "success") {
            audioPlayer.src = result.audio_url;
            audioPlayer.style.display = 'block';
            audioPlayer.play();
            statusMessage.innerText = "✅ Audio generated successfully!";
        } else {
            statusMessage.innerText = "❌ Error: " + result.message;
        }
    } catch (error) {
        statusMessage.innerText = "❌ Error: " + error;
    } finally {
        button.disabled = false;
    }
}
