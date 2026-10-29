/* Capture on the audio thread, independently of UI/model activity. */
class IrisCapture extends AudioWorkletProcessor {
  process(inputs) {
    const channel=inputs[0]?.[0];
    if(channel) this.port.postMessage(channel.slice());
    return true;
  }
}
registerProcessor('iris-capture',IrisCapture);
