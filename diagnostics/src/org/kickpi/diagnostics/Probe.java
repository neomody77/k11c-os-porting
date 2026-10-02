package org.kickpi.diagnostics;

import android.app.*;
import android.content.*;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.hardware.*;
import android.hardware.camera2.*;
import android.hardware.usb.*;
import android.media.*;
import android.opengl.*;
import android.os.*;
import android.security.keystore.*;
import android.webkit.*;
import java.io.*;
import java.net.*;
import java.nio.*;
import java.security.*;
import java.util.*;
import java.util.concurrent.*;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;
import org.json.*;

public class Probe extends Instrumentation {
  Bundle args;
  Context ctx;
  JSONObject result = new JSONObject();
  public void onCreate(Bundle b) { super.onCreate(b); args=b; start(); }
  void put(String key, Object value) throws Exception { result.put(key,value); }
  void require(boolean value, String why) { if(!value) throw new IllegalStateException(why); }
  public void onStart() {
    ctx=getTargetContext(); String test=args.getString("test","inventory"); long start=SystemClock.elapsedRealtime();
    try {
      put("test",test);
      switch(test) {
        case "storage": storage(); break;
        case "keystore": keystore(); break;
        case "gpu": gpu(); break;
        case "network": network(true); break;
        case "network-cold": network(false); break;
        case "sensor": sensor(); break;
        case "sensor-declarations": sensorDeclarations(); break;
        case "bluetooth-scan": bluetoothScan(); break;
        case "animation": animation(); break;
        case "video-hardware": decode(true,"video/"); break;
        case "video-hardware-1080p60": decode(true,"video/","sample-1080p60.mp4"); break;
        case "video-hardware-1080p60-bounded": decode(true,"video/","sample-1080p60-bounded.mp4"); break;
        case "video-hardware-1080p60-surface": decodeSurface(); break;
        case "video-software": decode(false,"video/"); break;
        case "audio-decode": decode(false,"audio/"); break;
        case "audio-play": audioPlay(); break;
        case "audio-record": audioRecord(); break;
        case "webview": webview(); break;
        default: inventory();
      }
      put("status","PASS");
    } catch(Throwable e) { try { put("status","FAIL");put("error",e.toString()); } catch(Exception ignored) {} }
    try { put("elapsed_ms",SystemClock.elapsedRealtime()-start); } catch(Exception ignored) {}
    Bundle b=new Bundle(); b.putString("stream",result.toString()+"\n"); finish(0,b);
  }
  void storage() throws Exception {
    File f=new File(ctx.getFilesDir(),"probe.bin"); byte[] chunk=new byte[1024*1024]; new Random(42).nextBytes(chunk);
    MessageDigest a=MessageDigest.getInstance("SHA-256"),b=MessageDigest.getInstance("SHA-256");
    long t=SystemClock.elapsedRealtime();
    try(FileOutputStream out=new FileOutputStream(f)) { for(int i=0;i<64;i++){out.write(chunk);a.update(chunk);} out.getFD().sync(); }
    put("write_fsync_ms",SystemClock.elapsedRealtime()-t);
    try(FileInputStream in=new FileInputStream(f)) {int n;while((n=in.read(chunk))!=-1)b.update(chunk,0,n);}
    require(Arrays.equals(a.digest(),b.digest()),"storage checksum mismatch"); require(f.delete(),"cannot delete test file");
    File dbFile=new File(ctx.getFilesDir(),"probe.db"); SQLiteDatabase db=SQLiteDatabase.openOrCreateDatabase(dbFile,null);
    try { db.execSQL("CREATE TABLE t (id INTEGER PRIMARY KEY, value TEXT)");db.beginTransaction();
      for(int i=0;i<1000;i++) db.execSQL("INSERT INTO t VALUES (?,?)",new Object[]{i,"row"+i});
      db.setTransactionSuccessful(); db.endTransaction();
      try(Cursor c=db.rawQuery("SELECT COUNT(*), SUM(id) FROM t",null)){c.moveToFirst();require(c.getInt(0)==1000&&c.getInt(1)==499500,"SQLite mismatch");}
    } finally {db.close(); SQLiteDatabase.deleteDatabase(dbFile);}
    put("bytes_verified",64*1024*1024);put("sqlite_rows_verified",1000);
  }
  void keystore() throws Exception {
    String alias="k11c-probe"; KeyStore ks=KeyStore.getInstance("AndroidKeyStore");ks.load(null);
    try {
      KeyGenerator g=KeyGenerator.getInstance("AES","AndroidKeyStore");g.init(new KeyGenParameterSpec.Builder(alias,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
      SecretKey key=g.generateKey();byte[] plain="K11C Android16 keystore roundtrip".getBytes("UTF-8");
      Cipher enc=Cipher.getInstance("AES/GCM/NoPadding");enc.init(Cipher.ENCRYPT_MODE,key);byte[] encrypted=enc.doFinal(plain);
      Cipher dec=Cipher.getInstance("AES/GCM/NoPadding");dec.init(Cipher.DECRYPT_MODE,key,new GCMParameterSpec(128,enc.getIV()));
      require(Arrays.equals(plain,dec.doFinal(encrypted)),"keystore mismatch");
      KeyInfo info=(KeyInfo)SecretKeyFactory.getInstance("AES","AndroidKeyStore").getKeySpec(key,KeyInfo.class);
      put("security_level",info.getSecurityLevel()); put("inside_secure_hardware",info.isInsideSecureHardware());
    } finally {ks.deleteEntry(alias);}
  }
  void gpu() throws Exception {
    EGLDisplay d=EGL14.eglGetDisplay(EGL14.EGL_DEFAULT_DISPLAY);int[] v=new int[2];require(EGL14.eglInitialize(d,v,0,v,1),"eglInitialize");
    EGLConfig[] configs=new EGLConfig[1];int[] n=new int[1];
    int[] attrs={EGL14.EGL_SURFACE_TYPE,EGL14.EGL_PBUFFER_BIT,EGL14.EGL_RENDERABLE_TYPE,EGL14.EGL_OPENGL_ES2_BIT,EGL14.EGL_RED_SIZE,8,EGL14.EGL_GREEN_SIZE,8,EGL14.EGL_BLUE_SIZE,8,EGL14.EGL_NONE};
    require(EGL14.eglChooseConfig(d,attrs,0,configs,0,1,n,0)&&n[0]>0,"eglChooseConfig");
    EGLContext c=EGL14.eglCreateContext(d,configs[0],EGL14.EGL_NO_CONTEXT,new int[]{EGL14.EGL_CONTEXT_CLIENT_VERSION,3,EGL14.EGL_NONE},0);
    EGLSurface s=EGL14.eglCreatePbufferSurface(d,configs[0],new int[]{EGL14.EGL_WIDTH,64,EGL14.EGL_HEIGHT,64,EGL14.EGL_NONE},0);
    try {
      require(EGL14.eglMakeCurrent(d,s,s,c),"eglMakeCurrent");put("renderer",GLES20.glGetString(GLES20.GL_RENDERER));put("version",GLES20.glGetString(GLES20.GL_VERSION));
      GLES20.glViewport(0,0,64,64);ByteBuffer pixel=ByteBuffer.allocateDirect(4);
      for(int i=0;i<300;i++){float r=(i%2==0)?1f:0f;GLES20.glClearColor(r,0.5f,0f,1f);GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT);GLES20.glFinish();pixel.clear();GLES20.glReadPixels(32,32,1,1,GLES20.GL_RGBA,GLES20.GL_UNSIGNED_BYTE,pixel);require((pixel.get(0)&255)==(r==1?255:0),"GPU red mismatch");require(Math.abs((pixel.get(1)&255)-128)<=1,"GPU green mismatch");require(GLES20.glGetError()==0,"GPU GL error");}
      put("frames_verified",300);
    } finally {EGL14.eglMakeCurrent(d,EGL14.EGL_NO_SURFACE,EGL14.EGL_NO_SURFACE,EGL14.EGL_NO_CONTEXT);EGL14.eglDestroySurface(d,s);EGL14.eglDestroyContext(d,c);EGL14.eglTerminate(d);}
  }
  void network(boolean awaitReady) throws Exception {
    android.net.ConnectivityManager cm=(android.net.ConnectivityManager)ctx.getSystemService(Context.CONNECTIVITY_SERVICE);
    if(awaitReady) {
      CountDownLatch ready=new CountDownLatch(1);
      android.net.ConnectivityManager.NetworkCallback callback=new android.net.ConnectivityManager.NetworkCallback(){
        boolean validated=false,blocked=true;
        void signalReady(){if(validated&&!blocked)ready.countDown();}
        @Override public synchronized void onCapabilitiesChanged(android.net.Network network,android.net.NetworkCapabilities caps){validated=caps.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_INTERNET)&&caps.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_VALIDATED);signalReady();}
        @Override public synchronized void onBlockedStatusChanged(android.net.Network network,boolean value){blocked=value;signalReady();}
        @Override public synchronized void onLost(android.net.Network network){validated=false;blocked=true;}
      };
      long start=SystemClock.elapsedRealtime();
      cm.registerDefaultNetworkCallback(callback);
      try {require(ready.await(5,TimeUnit.SECONDS),"default network not validated or UID still blocked");}
      finally {cm.unregisterNetworkCallback(callback);}
      put("network_ready_wait_ms",SystemClock.elapsedRealtime()-start);
    }
    put("uid",android.os.Process.myUid());put("active_network",String.valueOf(cm.getActiveNetwork()));
    boolean dnsOk=false;
    try {JSONArray dns=new JSONArray();for(InetAddress a:InetAddress.getAllByName("example.com"))dns.put(a.getHostAddress());put("dns",dns);dnsOk=true;}catch(Exception e){put("dns_error",e.toString());put("dns_cause",String.valueOf(e.getCause()));}
    HttpURLConnection c=(HttpURLConnection)new URL(dnsOk?"https://example.com/":"https://example.org/").openConnection();c.setConnectTimeout(10000);c.setReadTimeout(10000);
    try {int code=c.getResponseCode();put("https_status",code);require(code==200,"HTTPS status");int bytes=0;byte[] buf=new byte[4096];try(InputStream in=c.getInputStream()){int n;while((n=in.read(buf))!=-1)bytes+=n;}require(bytes>0,"empty HTTPS body");put("https_bytes",bytes);}finally{c.disconnect();}
    require(dnsOk,"DNS resolution failed");
  }
  void sensorDeclarations() throws Exception {
    SensorManager sm=(SensorManager)ctx.getSystemService(Context.SENSOR_SERVICE);
    boolean present=sm.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)!=null;
    boolean declared=ctx.getPackageManager().hasSystemFeature("android.hardware.sensor.accelerometer");
    put("sensor_count",sm.getSensorList(Sensor.TYPE_ALL).size());
    put("accelerometer_in_hal_list",present);put("accelerometer_feature",declared);
    require(present==declared,"accelerometer HAL list and feature disagree");
    put("physical_sampling_test",false);
  }
  void sensor() throws Exception {
    SensorManager sm=(SensorManager)ctx.getSystemService(Context.SENSOR_SERVICE);Sensor s=sm.getDefaultSensor(Sensor.TYPE_ACCELEROMETER);put("accelerometer_present",s!=null);put("accelerometer_feature",ctx.getPackageManager().hasSystemFeature("android.hardware.sensor.accelerometer"));require(s!=null,"no accelerometer");
    CountDownLatch done=new CountDownLatch(10);float[] last=new float[3];
    SensorEventListener l=new SensorEventListener(){public void onAccuracyChanged(Sensor sensor,int accuracy){}public void onSensorChanged(SensorEvent e){System.arraycopy(e.values,0,last,0,3);done.countDown();}};
    try {require(sm.registerListener(l,s,SensorManager.SENSOR_DELAY_NORMAL),"sensor registration failed");require(done.await(5,TimeUnit.SECONDS),"sensor event timeout");put("samples",10);put("xyz",new JSONArray(new double[]{last[0],last[1],last[2]}));}finally{sm.unregisterListener(l);}
  }
  void bluetoothScan() throws Exception {
    android.bluetooth.BluetoothManager bm=(android.bluetooth.BluetoothManager)ctx.getSystemService(Context.BLUETOOTH_SERVICE);
    android.bluetooth.BluetoothAdapter adapter=bm.getAdapter();require(adapter!=null&&adapter.isEnabled(),"Bluetooth not enabled");
    android.bluetooth.le.BluetoothLeScanner scanner=adapter.getBluetoothLeScanner();require(scanner!=null,"no BLE scanner");
    Set<String> peers=Collections.synchronizedSet(new HashSet<>());java.util.concurrent.atomic.AtomicInteger packets=new java.util.concurrent.atomic.AtomicInteger(),error=new java.util.concurrent.atomic.AtomicInteger();
    android.bluetooth.le.ScanCallback callback=new android.bluetooth.le.ScanCallback(){public void onScanResult(int type,android.bluetooth.le.ScanResult r){peers.add(r.getDevice().getAddress());packets.incrementAndGet();}public void onScanFailed(int code){error.set(code);}};
    try {scanner.startScan(null,new android.bluetooth.le.ScanSettings.Builder().setScanMode(android.bluetooth.le.ScanSettings.SCAN_MODE_LOW_LATENCY).build(),callback);SystemClock.sleep(10000);require(error.get()==0,"BLE scan failed "+error.get());put("packets",packets.get());put("unique_devices",peers.size());put("rf_reception_verified",packets.get()>0);}finally{scanner.stopScan(callback);}
  }
  void animation() throws Exception {
    Activity a=startActivitySync(new Intent(ctx,ProbeActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
    List<Long> times=Collections.synchronizedList(new ArrayList<>()),totals=Collections.synchronizedList(new ArrayList<>()),gpuTimes=Collections.synchronizedList(new ArrayList<>());
    HandlerThread thread=new HandlerThread("FrameMetrics");thread.start();
    android.view.Window.OnFrameMetricsAvailableListener listener=(window,metrics,dropped)->{totals.add(metrics.getMetric(android.view.FrameMetrics.TOTAL_DURATION));gpuTimes.add(metrics.getMetric(android.view.FrameMetrics.GPU_DURATION));};
    android.view.View[] view=new android.view.View[1];
    try {
      runOnMainSync(()->{a.getWindow().addOnFrameMetricsAvailableListener(listener,new Handler(thread.getLooper()));view[0]=new android.view.View(a){android.graphics.Paint paint=new android.graphics.Paint();protected void onDraw(android.graphics.Canvas canvas){long t=System.nanoTime();times.add(t);canvas.drawColor(0xff102030);for(int i=0;i<100;i++){paint.setColor(0xff000000|((i*167771+times.size()*500)&0xffffff));float x=(times.size()*4+i*37)%getWidth(),y=(i*41)%getHeight();canvas.drawRect(x,y,x+24,y+24,paint);}paint.setColor(0xffffffff);paint.setTextSize(30);canvas.drawText("K11C Android16 continuous animation",20,50,paint);postInvalidateOnAnimation();}};a.setContentView(view[0]);});
      SystemClock.sleep(15000);
      List<Long> captured;synchronized(times){captured=new ArrayList<>(times);}require(captured.size()>100,"too few rendered frames");
      put("frames_drawn",captured.size());put("rendered_fps",(captured.size()-1)*1e9/(captured.get(captured.size()-1)-captured.get(0)));
      List<Double> intervals=new ArrayList<>();for(int i=1;i<captured.size();i++)intervals.add((captured.get(i)-captured.get(i-1))/1e6);Collections.sort(intervals);put("interval_p50_ms",intervals.get(intervals.size()/2));put("interval_p95_ms",intervals.get((int)(intervals.size()*0.95)));put("interval_max_ms",intervals.get(intervals.size()-1));
      List<Long> durations;synchronized(totals){durations=new ArrayList<>(totals);}Collections.sort(durations);if(!durations.isEmpty())put("frame_duration_p95_ms",durations.get((int)(durations.size()*0.95))/1e6);
      put("display_refresh_hz",a.getDisplay().getRefreshRate());put("hardware_accelerated",view[0].isHardwareAccelerated());
    } finally {runOnMainSync(()->{a.getWindow().removeOnFrameMetricsAvailableListener(listener);a.finish();});thread.quitSafely();}
  }
  void decode(boolean hardware,String prefix) throws Exception {
    decode(hardware,prefix,"sample.mp4");
  }
  void decode(boolean hardware,String prefix,String asset) throws Exception {
    decode(hardware,prefix,asset,null);
  }
  void decodeSurface() throws Exception {
    Activity a=startActivitySync(new Intent(ctx,ProbeActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
    android.view.SurfaceView[] view=new android.view.SurfaceView[1];CountDownLatch ready=new CountDownLatch(1);
    try {
      runOnMainSync(()->{view[0]=new android.view.SurfaceView(a);view[0].getHolder().addCallback(new android.view.SurfaceHolder.Callback(){public void surfaceCreated(android.view.SurfaceHolder h){ready.countDown();}public void surfaceChanged(android.view.SurfaceHolder h,int f,int w,int height){}public void surfaceDestroyed(android.view.SurfaceHolder h){}});a.setContentView(view[0]);});
      require(ready.await(10,TimeUnit.SECONDS),"Surface not ready");decode(true,"video/","sample-1080p60.mp4",view[0].getHolder().getSurface());
    }finally{runOnMainSync(a::finish);}
  }
  void decode(boolean hardware,String prefix,String asset,android.view.Surface surface) throws Exception {
    File f=new File(ctx.getFilesDir(),"sample.mp4");try(InputStream in=ctx.getAssets().open(asset);FileOutputStream out=new FileOutputStream(f)){byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1)out.write(b,0,n);}
    MediaExtractor ex=new MediaExtractor();MediaCodec codec=null;
    try {
      ex.setDataSource(f.getAbsolutePath());int track=-1;MediaFormat format=null;String mime=null;
      for(int i=0;i<ex.getTrackCount();i++){MediaFormat fmt=ex.getTrackFormat(i);String m=fmt.getString(MediaFormat.KEY_MIME);if(m.startsWith(prefix)){track=i;format=fmt;mime=m;break;}}
      require(track>=0,"no sample track");String name=null,fallback=null;JSONArray names=new JSONArray();
      for(MediaCodecInfo ci:new MediaCodecList(MediaCodecList.ALL_CODECS).getCodecInfos())if(!ci.isEncoder())for(String m:ci.getSupportedTypes())if(m.equals(mime)){names.put(ci.getName());if(ci.isHardwareAccelerated()==hardware){if(fallback==null)fallback=ci.getName();if(name==null&&ci.getCapabilitiesForType(m).isFormatSupported(format))name=ci.getName();}}
      put("declared_format_supported",name!=null);if(name==null)name=fallback;
      if(asset.equals("sample-1080p60-bounded.mp4")) {
        String automatic=new MediaCodecList(MediaCodecList.REGULAR_CODECS).findDecoderForFormat(format);
        put("automatic_decoder",automatic);require(name!=null&&name.equals(automatic),"automatic selection did not choose declared hardware decoder");
      }
      if(mime.startsWith("video/")) {
        MediaCodecInfo.CodecCapabilities caps=null;
        for(MediaCodecInfo ci:new MediaCodecList(MediaCodecList.ALL_CODECS).getCodecInfos())if(ci.getName().equals(name))caps=ci.getCapabilitiesForType(mime);
        if(caps!=null) {
          JSONObject checks=new JSONObject();JSONArray levels=new JSONArray();
          for(MediaCodecInfo.CodecProfileLevel pl:caps.profileLevels)levels.put(new JSONObject().put("profile",pl.profile).put("level",pl.level));
          checks.put("profile_levels",levels);checks.put("bitrate_range",caps.getVideoCapabilities().getBitrateRange().toString());
          MediaFormat base=MediaFormat.createVideoFormat(mime,format.getInteger(MediaFormat.KEY_WIDTH),format.getInteger(MediaFormat.KEY_HEIGHT));
          checks.put("size",caps.isFormatSupported(base));
          base.setFloat(MediaFormat.KEY_FRAME_RATE,format.getNumber(MediaFormat.KEY_FRAME_RATE).floatValue());checks.put("size_and_rate",caps.isFormatSupported(base));
          for(String key:new String[]{MediaFormat.KEY_BIT_RATE,MediaFormat.KEY_PROFILE,MediaFormat.KEY_LEVEL})if(format.containsKey(key)) {
            base.setInteger(key,format.getInteger(key));checks.put("with_"+key,caps.isFormatSupported(base));base.removeKey(key);
          }
          checks.put("full",caps.isFormatSupported(format));put("capability_checks",checks);
          if(asset.equals("sample-1080p60-bounded.mp4"))require(caps.isFormatSupported(format),"bounded sample outside declared capability");
        }
      }
      put("input_format",format.toString());put("available",names);require(name!=null,"no matching "+(hardware?"hardware":"software")+" decoder");put("codec",name);put("mime",mime);ex.selectTrack(track);
      put("output_mode",surface==null?"YUV ByteBuffer":"Surface");codec=MediaCodec.createByCodecName(name);codec.configure(format,surface,null,0);codec.start();boolean inDone=false,outDone=false;int frames=0;long bytes=0,decodeStart=SystemClock.elapsedRealtime(),end=decodeStart+20000;MediaCodec.BufferInfo info=new MediaCodec.BufferInfo();
      while(!outDone&&SystemClock.elapsedRealtime()<end){
        if(!inDone){int index=codec.dequeueInputBuffer(10000);if(index>=0){ByteBuffer b=codec.getInputBuffer(index);int size=ex.readSampleData(b,0);if(size<0){codec.queueInputBuffer(index,0,0,0,MediaCodec.BUFFER_FLAG_END_OF_STREAM);inDone=true;}else{codec.queueInputBuffer(index,0,size,ex.getSampleTime(),0);ex.advance();}}}
        int index=codec.dequeueOutputBuffer(info,10000);if(index>=0){if(info.size>0||(surface!=null&&(info.flags&MediaCodec.BUFFER_FLAG_END_OF_STREAM)==0)){frames++;bytes+=info.size;}outDone=(info.flags&MediaCodec.BUFFER_FLAG_END_OF_STREAM)!=0;codec.releaseOutputBuffer(index,surface!=null);}
      }
      require(outDone&&frames>0,"decoder timeout or no frames");put("output_buffers",frames);put("output_bytes",bytes);put("eos",outDone);put("decode_ms",SystemClock.elapsedRealtime()-decodeStart);
    } finally {if(codec!=null){try{codec.stop();}finally{codec.release();}}ex.release();f.delete();}
  }
  void audioPlay() throws Exception {
    int rate=48000;short[] pcm=new short[rate];for(int i=0;i<pcm.length;i++)pcm[i]=(short)(Math.sin(2*Math.PI*440*i/rate)*3000);
    AudioTrack t=new AudioTrack.Builder().setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build()).setAudioFormat(new AudioFormat.Builder().setSampleRate(rate).setEncoding(AudioFormat.ENCODING_PCM_16BIT).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build()).setTransferMode(AudioTrack.MODE_STATIC).setBufferSizeInBytes(pcm.length*2).build();
    try{require(t.write(pcm,0,pcm.length)==pcm.length,"short AudioTrack write");require(t.getState()==AudioTrack.STATE_INITIALIZED,"AudioTrack not initialized after data write");t.play();SystemClock.sleep(1600);int head=t.getPlaybackHeadPosition();put("playback_frames",head);require(head>=rate,"audio playback did not advance");}finally{t.release();}
  }
  void audioRecord() throws Exception {
    int rate=48000,min=AudioRecord.getMinBufferSize(rate,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT);
    AudioRecord r=new AudioRecord(MediaRecorder.AudioSource.MIC,rate,AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT,Math.max(min,rate*2));
    try{require(r.getState()==AudioRecord.STATE_INITIALIZED,"AudioRecord not initialized");r.startRecording();short[] b=new short[rate];int total=0;double sum=0;long end=SystemClock.elapsedRealtime()+5000;while(total<rate&&SystemClock.elapsedRealtime()<end){int n=r.read(b,0,Math.min(b.length,rate-total),AudioRecord.READ_NON_BLOCKING);require(n>=0,"AudioRecord read error "+n);for(int i=0;i<n;i++)sum+=(double)b[i]*b[i];total+=n;if(n==0)SystemClock.sleep(10);}put("capture_samples",total);put("rms",total>0?Math.sqrt(sum/total):0);require(total>=rate,"capture did not advance");}finally{r.release();}
  }
  void inventory() throws Exception {
    JSONArray cams=new JSONArray(),sensors=new JSONArray(),usb=new JSONArray();CameraManager cm=(CameraManager)ctx.getSystemService(Context.CAMERA_SERVICE);
    for(String id:cm.getCameraIdList())cams.put(id);for(Sensor s:((SensorManager)ctx.getSystemService(Context.SENSOR_SERVICE)).getSensorList(Sensor.TYPE_ALL))sensors.put(s.getName());
    for(UsbDevice d:((UsbManager)ctx.getSystemService(Context.USB_SERVICE)).getDeviceList().values())usb.put(d.getVendorId()+":"+d.getProductId());
    put("camera_ids",cams);put("sensors",sensors);put("usb_host_devices",usb);put("abis",new JSONArray(Arrays.asList(Build.SUPPORTED_ABIS)));put("api",Build.VERSION.SDK_INT);
  }
  void webview() throws Exception {
    Activity a=startActivitySync(new Intent(ctx,ProbeActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));CountDownLatch done=new CountDownLatch(1);String[] value=new String[1];WebView[] w=new WebView[1];
    try {
      runOnMainSync(()->{w[0]=new WebView(a);a.setContentView(w[0]);w[0].getSettings().setJavaScriptEnabled(true);w[0].setWebViewClient(new WebViewClient(){public void onPageFinished(WebView view,String url){view.evaluateJavascript("document.getElementById('probe').textContent + ':' + (6*7)",v->{value[0]=v;done.countDown();});}});w[0].loadDataWithBaseURL("https://example.com/","<html><body><div id='probe'>K11C</div></body></html>","text/html","UTF-8",null);});
      require(done.await(15,TimeUnit.SECONDS),"WebView load timeout");require("\"K11C:42\"".equals(value[0]),"WebView JS mismatch "+value[0]);put("javascript_result",value[0]);
    } finally {runOnMainSync(()->{if(w[0]!=null)w[0].destroy();a.finish();});}
  }
}
