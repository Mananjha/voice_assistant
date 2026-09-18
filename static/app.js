const callButton = document.getElementById("callButton");
const endButton = document.getElementById("endButton");
const statusElement = document.getElementById("status");
const instructionElement = document.getElementById("instruction");
const callIcon = document.getElementById("callIcon");
const conversationElement = document.getElementById("conversation");

let peerConnection = null;
let localStream = null;
let sessionId = null;
let remoteAudio = null;

let callActive = false;
let stoppingCall = false;


console.log("========================================");
console.log("Naikroop AI Voice Assistant JS loaded.");
console.log("========================================");

console.log({
    callButton,
    endButton,
    statusElement,
    instructionElement,
    callIcon,
    conversationElement
});

if (!callButton) {
    console.error("ERROR: #callButton was not found.");
}

if (!endButton) {
    console.error("ERROR: #endButton was not found.");
}

function createRemoteAudio() {

    if (remoteAudio) {
        return remoteAudio;
    }

    remoteAudio = document.createElement("audio");

    remoteAudio.id = "remoteAudio";

    remoteAudio.autoplay = true;
    remoteAudio.playsInline = true;
    remoteAudio.controls = false;

    remoteAudio.style.display = "none";

    document.body.appendChild(remoteAudio);

    console.log("Remote audio element created.");

    return remoteAudio;
}

async function startRemoteAudio(stream) {

    const audio = createRemoteAudio();

    try {

        audio.srcObject = stream;

        console.log(
            "Remote audio stream attached."
        );

        await audio.play();

        console.log(
            "Remote audio playback started."
        );

    } catch (error) {

        console.warn(
            "Audio autoplay/playback warning:",
            error
        );

        audio.onloadedmetadata = async () => {

            try {

                await audio.play();

                console.log(
                    "Remote audio playback started after metadata."
                );

            } catch (retryError) {

                console.error(
                    "Remote audio playback failed:",
                    retryError
                );
            }
        };
    }
}

if (callButton) {

    callButton.addEventListener(
        "click",
        startCall
    );
}


async function startCall() {

    if (callActive) {
        return;
    }

    if (stoppingCall) {
        return;
    }

    try {

        callActive = true;
        stoppingCall = false;

        statusElement.textContent =
            "Requesting microphone...";

        instructionElement.textContent =
            "Please allow microphone access.";

        callButton.disabled = true;

        console.log(
            "Requesting microphone..."
        );

        localStream =
            await navigator.mediaDevices.getUserMedia({

                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,

                    channelCount: 1
                },

                video: false
            });

        console.log(
            "Microphone access granted."
        );

        peerConnection =
            new RTCPeerConnection();

        console.log(
            "PeerConnection created."
        );

        localStream
            .getTracks()
            .forEach((track) => {

                console.log(
                    "Adding microphone track:",
                    track.kind
                );

                peerConnection.addTrack(
                    track,
                    localStream
                );
            });

        peerConnection.ontrack =
            async (event) => {

                console.log(
                    "========================================"
                );

                console.log(
                    "Received remote WebRTC audio track."
                );

                console.log(
                    "Track kind:",
                    event.track.kind
                );

                console.log(
                    "Streams:",
                    event.streams
                );

                console.log(
                    "========================================"
                );


                if (
                    event.track.kind !==
                    "audio"
                ) {
                    return;
                }

                let stream = null;

                if (
                    event.streams &&
                    event.streams.length > 0
                ) {

                    stream =
                        event.streams[0];

                } else {
                    stream =
                        new MediaStream([
                            event.track
                        ]);
                }

                await startRemoteAudio(
                    stream
                );

                event.track.onended = () => {

                    console.log(
                        "Remote audio track ended."
                    );
                };

                event.track.onmute = () => {

                    console.log(
                        "Remote audio track muted."
                    );
                };

                event.track.onunmute = () => {

                    console.log(
                        "Remote audio track unmuted."
                    );
                };
            };

        peerConnection.onconnectionstatechange =
            () => {

                if (!peerConnection) {
                    return;
                }

                const state =
                    peerConnection.connectionState;

                console.log(
                    "WebRTC connection state:",
                    state
                );

                if (state === "connected") {

                    console.log(
                        "WebRTC connection established."
                    );

                    statusElement.textContent =
                        "Call connected";

                    instructionElement.textContent =
                        "Naikroop AI is ready. You can speak now.";

                    callIcon.classList.add(
                        "active"
                    );

                    callButton.classList.add(
                        "hidden"
                    );

                    endButton.classList.remove(
                        "hidden"
                    );
                }

                if (state === "failed") {

                    console.error(
                        "WebRTC connection failed."
                    );

                    statusElement.textContent =
                        "Connection failed";

                    instructionElement.textContent =
                        "The voice connection could not be established.";

                    stopCall();
                }

                if (state === "closed") {

                    console.log(
                        "WebRTC connection closed."
                    );
                }
            };

        peerConnection.oniceconnectionstatechange =
            () => {

                if (!peerConnection) {
                    return;
                }

                console.log(
                    "ICE connection state:",
                    peerConnection.iceConnectionState
                );
            };

        console.log(
            "Creating WebRTC offer..."
        );

        const offer =
            await peerConnection.createOffer({

                offerToReceiveAudio: true,

                offerToReceiveVideo: false
            });


        await peerConnection.setLocalDescription(
            offer
        );

        console.log(
            "Local description created."
        );

        console.log(
            "Waiting for ICE gathering..."
        );

        await waitForIceGatheringComplete(
            peerConnection
        );

        console.log(
            "ICE gathering complete."
        );

        statusElement.textContent =
            "Connecting...";

        console.log(
            "Sending WebRTC offer to server..."
        );


        const response =
            await fetch(
                "/webrtc/offer",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({

                        sdp:
                            peerConnection
                                .localDescription
                                .sdp,

                        type:
                            peerConnection
                                .localDescription
                                .type
                    })
                }
            );


        console.log(
            "Server response status:",
            response.status
        );

        if (!response.ok) {

            throw new Error(
                `WebRTC server error: ${response.status}`
            );
        }

        const answer =
            await response.json();


        console.log(
            "Received WebRTC answer:",
            answer
        );


        if (
            !answer.session_id ||
            !answer.sdp ||
            !answer.type
        ) {

            throw new Error(
                "Invalid WebRTC answer received from server."
            );
        }


        sessionId =
            answer.session_id;


        console.log(
            "Session ID:",
            sessionId
        );

        await peerConnection.setRemoteDescription({

            type: answer.type,

            sdp: answer.sdp
        });


        console.log(
            "Remote description set."
        );

        callButton.classList.add(
            "hidden"
        );

        callButton.disabled = false;

        endButton.classList.remove(
            "hidden"
        );

        callIcon.classList.add(
            "active"
        );

        statusElement.textContent =
            "Call connected";

        instructionElement.textContent =
            "Naikroop AI is speaking. Please wait for the greeting.";


        console.log(
            "========================================"
        );

        console.log(
            "CALL STARTED SUCCESSFULLY"
        );

        console.log(
            "Session:",
            sessionId
        );

        console.log(
            "========================================"
        );

    }

    catch (error) {

        console.error(
            "========================================"
        );

        console.error(
            "CALL ERROR:",
            error
        );

        console.error(
            "========================================"
        );


        statusElement.textContent =
            "Could not start call";

        instructionElement.textContent =
            error.message ||
            "Unable to start voice call.";


        callButton.disabled = false;

        await stopCall();
    }
}

function waitForIceGatheringComplete(
    pc
) {

    return new Promise((resolve) => {

        if (
            pc.iceGatheringState ===
            "complete"
        ) {

            resolve();

            return;
        }


        const checkState = () => {

            console.log(
                "ICE gathering state:",
                pc.iceGatheringState
            );


            if (
                pc.iceGatheringState ===
                "complete"
            ) {

                pc.removeEventListener(
                    "icegatheringstatechange",
                    checkState
                );

                resolve();
            }
        };


        pc.addEventListener(
            "icegatheringstatechange",
            checkState
        );


        setTimeout(() => {

            pc.removeEventListener(
                "icegatheringstatechange",
                checkState
            );

            console.warn(
                "ICE gathering timeout. Continuing."
            );

            resolve();

        }, 3000);
    });
}

if (endButton) {

    endButton.addEventListener(
        "click",
        stopCall
    );
}

async function stopCall() {

    if (stoppingCall) {
        return;
    }

    stoppingCall = true;

    console.log(
        "========================================"
    );

    console.log(
        "Stopping call..."
    );

    console.log(
        "========================================"
    );


    callActive = false;

    if (sessionId) {

        const currentSession =
            sessionId;

        sessionId = null;


        try {

            console.log(
                "Closing backend session:",
                currentSession
            );


            await fetch(
                `/webrtc/${currentSession}/close`,
                {
                    method: "POST"
                }
            );


            console.log(
                "Backend session closed."
            );

        }

        catch (error) {

            console.warn(
                "Close request error:",
                error
            );
        }
    }

    if (localStream) {

        console.log(
            "Stopping microphone..."
        );


        localStream
            .getTracks()
            .forEach((track) => {

                track.stop();
            });


        localStream = null;
    }

    if (peerConnection) {

        console.log(
            "Closing PeerConnection..."
        );


        try {

            peerConnection.close();

        }

        catch (error) {

            console.warn(
                "PeerConnection close error:",
                error
            );
        }


        peerConnection = null;
    }


    if (remoteAudio) {

        try {

            remoteAudio.pause();

            remoteAudio.srcObject = null;

            remoteAudio.remove();

        }

        catch (error) {

            console.warn(
                "Remote audio cleanup error:",
                error
            );
        }


        remoteAudio = null;
    }

    if (callButton) {

        callButton.classList.remove(
            "hidden"
        );

        callButton.disabled = false;
    }


    if (endButton) {

        endButton.classList.add(
            "hidden"
        );
    }


    if (callIcon) {

        callIcon.classList.remove(
            "active"
        );
    }


    if (statusElement) {

        statusElement.textContent =
            "Call ended";
    }


    if (instructionElement) {

        instructionElement.textContent =
            "Click 'Call Naikroop AI' to call again.";
    }


    stoppingCall = false;


    console.log(
        "Call completely stopped."
    );
}