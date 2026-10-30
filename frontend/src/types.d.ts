/// <reference types="vite/client" />
declare module '@novnc/novnc' {
  export default class RFB extends EventTarget {
    constructor(target:HTMLElement,url:string,options?:object);
    viewOnly:boolean;scaleViewport:boolean;resizeSession:boolean;qualityLevel:number;compressionLevel:number;showDotCursor:boolean;
    disconnect():void;getImageData():ImageData;
  }
}
