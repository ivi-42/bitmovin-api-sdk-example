import com.bitmovin.api.sdk.BitmovinApi;
import com.bitmovin.api.sdk.common.BitmovinException;
import com.bitmovin.api.sdk.model.AacAudioConfiguration;
import com.bitmovin.api.sdk.model.Ac3AudioConfiguration;
import com.bitmovin.api.sdk.model.AclEntry;
import com.bitmovin.api.sdk.model.AclPermission;
import com.bitmovin.api.sdk.model.CodecConfiguration;
import com.bitmovin.api.sdk.model.Encoding;
import com.bitmovin.api.sdk.model.EncodingOutput;
import com.bitmovin.api.sdk.model.H264VideoConfiguration;
import com.bitmovin.api.sdk.model.H265VideoConfiguration;
import com.bitmovin.api.sdk.model.HttpInput;
import com.bitmovin.api.sdk.model.MessageType;
import com.bitmovin.api.sdk.model.Mp4Muxing;
import com.bitmovin.api.sdk.model.MuxingStream;
import com.bitmovin.api.sdk.model.Output;
import com.bitmovin.api.sdk.model.PresetConfiguration;
import com.bitmovin.api.sdk.model.ProgressiveTsMuxing;
import com.bitmovin.api.sdk.model.S3Output;
import com.bitmovin.api.sdk.model.StartEncodingRequest;
import com.bitmovin.api.sdk.model.Status;
import com.bitmovin.api.sdk.model.Stream;
import com.bitmovin.api.sdk.model.StreamInput;
import com.bitmovin.api.sdk.model.StreamSelectionMode;
import com.bitmovin.api.sdk.model.Task;
import common.ConfigProvider;
import feign.Logger.Level;
import feign.slf4j.Slf4jLogger;
import java.nio.file.Paths;
import java.util.Arrays;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * This example demonstrates how to use different codecs and muxing types in a single encoding.
 *
 * <p>The following configuration parameters are expected:
 *
 * <ul>
 *   <li>BITMOVIN_API_KEY - Your API key for the Bitmovin API
 *   <li>HTTP_INPUT_HOST - The Hostname or IP address of the HTTP server hosting your input files,
 *       e.g.: my-storage.biz
 *   <li>HTTP_INPUT_FILE_PATH - The path to your input file on the provided HTTP server Example:
 *       videos/1080p_Sintel.mp4
 *   <li>S3_OUTPUT_BUCKET_NAME - The name of your S3 output bucket. Example: my-bucket-name
 *   <li>S3_OUTPUT_ACCESS_KEY - The access key of your S3 output bucket
 *   <li>S3_OUTPUT_SECRET_KEY - The secret key of your S3 output bucket
 *   <li>S3_OUTPUT_BASE_PATH - The base path on your S3 output bucket where content will be written.
 *       Example: /outputs
 * </ul>
 *
 * <p>Configuration parameters will be retrieved from these sources in the listed order:
 *
 * <ol>
 *   <li>command line arguments (eg BITMOVIN_API_KEY=xyz)
 *   <li>properties file located in the root folder of the JAVA examples at ./examples.properties
 *       (see examples.properties.template as reference)
 *   <li>environment variables
 *   <li>properties file located in the home folder at ~/.bitmovin/examples.properties (see
 *       examples.properties.template as reference)
 * </ol>
 */
public class MultiCodecEncoding {

  private static final Logger logger = LoggerFactory.getLogger(MultiCodecEncoding.class);

  private static BitmovinApi bitmovinApi;
  private static ConfigProvider configProvider;

  public static void main(String[] args) throws Exception {
    configProvider = new ConfigProvider(args);
    bitmovinApi =
        BitmovinApi.builder()
            .withApiKey(configProvider.getBitmovinApiKey())
            .withLogger(
                new Slf4jLogger(), Level.BASIC) // set the logger and log level for the API client
            .build();

    Encoding encoding =
        createEncoding("Multi codec encoding", "Encoding with H.264, H.265 and VP9");

    HttpInput input = createHttpInput(configProvider.getHttpInputHost());
    Output output =
        createS3Output(
            configProvider.getS3OutputBucketName(),
            configProvider.getS3OutputAccessKey(),
            configProvider.getS3OutputSecretKey());

    String inputFilePath = configProvider.getHttpInputFilePath();

    // Add an H.264 video stream to the encoding
    H264VideoConfiguration h264Config = createH264VideoConfig();
    Stream h264VideoStream = createStream(encoding, input, inputFilePath, h264Config);

    // Add an H.265 video stream to the encoding
    H265VideoConfiguration h265Config = createH265VideoConfig();
    Stream h265VideoStream = createStream(encoding, input, inputFilePath, h265Config);

    // Add an AAC audio stream to the encoding
    AacAudioConfiguration aacConfig = createAacAudioConfig();
    Stream aacAudioStream = createStream(encoding, input, inputFilePath, aacConfig);

    // Add an AC3 audio stream to the encoding
    Ac3AudioConfiguration ac3Config = createAc3AudioConfig();
    Stream ac3AudioStream = createStream(encoding, input, inputFilePath, ac3Config);

    // Create an MP4 muxing with the H.264 and AAC streams
    createMp4Muxing(
        encoding,
        output,
        "mp4-h264-aac",
        Arrays.asList(h264VideoStream, aacAudioStream),
        "video.mp4");

    // Create an MP4 muxing with the H.265 and AC3 streams
    createMp4Muxing(
        encoding,
        output,
        "mp4-h265-ac3",
        Arrays.asList(h265VideoStream, ac3AudioStream),
        "video.mp4");

    // Create a progressive TS muxing with the H.264 and AAC streams
    createProgressiveTsMuxing(
        encoding,
        output,
        "progressivets-h264-aac",
        Arrays.asList(h264VideoStream, aacAudioStream),
        "video.ts");

    executeEncoding(encoding);
  }

  /**
   * Creates a resource representing an HTTP server providing the input files. For alternative input
   * methods see <a
   * href="https://bitmovin.com/docs/encoding/articles/supported-input-output-storages">list of
   * supported input and output storages</a>
   *
   * <p>For reasons of simplicity, a new input resource is created on each execution of this
   * example. In production use, this method should be replaced by a <a
   * href="https://bitmovin.com/docs/encoding/api-reference/sections/inputs#/Encoding/GetEncodingInputsHttpByInputId">get
   * call</a> to retrieve an existing resource.
   *
   * <p>API endpoint:
   * https://bitmovin.com/docs/encoding/api-reference/sections/inputs#/Encoding/PostEncodingInputsHttp
   *
   * @param host The hostname or IP address of the HTTP server e.g.: my-storage.biz
   */
  private static HttpInput createHttpInput(String host) throws BitmovinException {
    HttpInput input = new HttpInput();
    input.setHost(host);

    return bitmovinApi.encoding.inputs.http.create(input);
  }

  /**
   * Creates a resource representing an AWS S3 cloud storage bucket to which generated content will
   * be transferred. For alternative output methods see <a
   * href="https://bitmovin.com/docs/encoding/articles/supported-input-output-storages">list of
   * supported input and output storages</a>
   *
   * <p>The provided credentials need to allow <i>read</i>, <i>write</i> and <i>list</i> operations.
   * <i>delete</i> should also be granted to allow overwriting of existings files. See <a
   * href="https://bitmovin.com/docs/encoding/faqs/how-do-i-create-a-aws-s3-bucket-which-can-be-used-as-output-location">creating
   * an S3 bucket and setting permissions</a> for further information
   *
   * <p>For reasons of simplicity, a new output resource is created on each execution of this
   * example. In production use, this method should be replaced by a <a
   * href="https://bitmovin.com/docs/encoding/api-reference/sections/outputs#/Encoding/GetEncodingOutputsS3">get
   * call</a> retrieving an existing resource.
   *
   * <p>API endpoint:
   * https://bitmovin.com/docs/encoding/api-reference/sections/outputs#/Encoding/PostEncodingOutputsS3
   *
   * @param bucketName The name of the S3 bucket
   * @param accessKey The access key of your S3 account
   * @param secretKey The secret key of your S3 account
   */
  private static S3Output createS3Output(String bucketName, String accessKey, String secretKey)
      throws BitmovinException {

    S3Output s3Output = new S3Output();
    s3Output.setBucketName(bucketName);
    s3Output.setAccessKey(accessKey);
    s3Output.setSecretKey(secretKey);

    return bitmovinApi.encoding.outputs.s3.create(s3Output);
  }

  /**
   * Creates an Encoding object. This is the base object to configure your encoding.
   *
   * <p>API endpoint:
   * https://bitmovin.com/docs/encoding/api-reference/sections/encodings#/Encoding/PostEncodingEncodings
   *
   * @param name This is the name of the encoding
   * @param description This is the description of the encoding
   */
  private static Encoding createEncoding(String name, String description) throws BitmovinException {
    Encoding encoding = new Encoding();
    encoding.setName(name);
    encoding.setDescription(description);

    return bitmovinApi.encoding.encodings.create(encoding);
  }

  /**
   * Creates a stream which binds an input file to a codec configuration. The stream is used for
   * muxings later on.
   *
   * <p>API endpoint:
   * https://bitmovin.com/docs/encoding/api-reference/sections/encodings#/Encoding/PostEncodingEncodingsStreamsByEncodingId
   *
   * @param encoding The encoding to add the stream onto
   * @param input The input that should be used
   * @param inputPath The path to the input file
   * @param codecConfiguration The codec configuration to be applied to the stream
   */
  private static Stream createStream(
      Encoding encoding, HttpInput input, String inputPath, CodecConfiguration codecConfiguration)
      throws BitmovinException {
    StreamInput streamInput = new StreamInput();
    streamInput.setInputId(input.getId());
    streamInput.setInputPath(inputPath);
    streamInput.setSelectionMode(StreamSelectionMode.AUTO);

    Stream stream = new Stream();
    stream.addInputStreamsItem(streamInput);
    stream.setCodecConfigId(codecConfiguration.getId());

    return bitmovinApi.encoding.encodings.streams.create(encoding.getId(), stream);
  }

  /**
   * Creates a configuration for the H.264 video codec to be applied to video streams.
   *
   * <p>The output resolution is defined by setting the height to 1080 pixels. Width will be
   * determined automatically to maintain the aspect ratio of your input video.
   *
   * <p>To keep things simple, we use a quality-optimized VoD preset configuration, which will apply
   * proven settings for the codec. See <a
   * href="https://bitmovin.com/docs/encoding/tutorials/how-to-optimize-your-h264-codec-configuration-for-different-use-cases">How
   * to optimize your H264 codec configuration for different use-cases</a> for alternative presets.
   *
   * <p>API endpoint:
   * https://bitmovin.com/docs/encoding/api-reference/sections/configurations#/Encoding/PostEncodingConfigurationsVideoH264
   */
  private static H264VideoConfiguration createH264VideoConfig() throws BitmovinException {
    H264VideoConfiguration config = new H264VideoConfiguration();
    config.setName("H.264 1080p 1.5 Mbit/s");
    config.setPresetConfiguration(PresetConfiguration.VOD_STANDARD);
    config.setHeight(1080);
    config.setBitrate(1_500_000L);

    return bitmovinApi.encoding.configurations.video.h264.create(config);
  }

  /**
   * Creates a base H.265 video configuration. The width of the video will be set accordingly to the
   * aspect ratio of the source video.
   *
   * <p>API endpoint:
   * https://bitmovin.com/docs/encoding/api-reference/sections/configurations#/Encoding/PostEncodingConfigurationsVideoH265
   */
  private static H265VideoConfiguration createH265VideoConfig() throws BitmovinException {
    H265VideoConfiguration config = new H265VideoConfiguration();
    config.setName("H.265 video config");
    config.setPresetConfiguration(PresetConfiguration.VOD_STANDARD);
    config.setHeight(1080);
    config.setBitrate(1_500_000L);

    return bitmovinApi.encoding.configurations.video.h265.create(config);
  }

  /**
   * Creates a configuration for the AAC audio codec to be applied to audio streams.
   *
   * <p>API endpoint:
   * https://bitmovin.com/docs/encoding/api-reference/sections/configurations#/Encoding/PostEncodingConfigurationsAudioAac
   */
  private static AacAudioConfiguration createAacAudioConfig() throws BitmovinException {
    AacAudioConfiguration config = new AacAudioConfiguration();
    config.setName("AAC 128 kbit/s");
    config.setBitrate(128_000L);

    return bitmovinApi.encoding.configurations.audio.aac.create(config);
  }

  /**
   * Creates an AC3 audio configuration. The sample rate of the audio will be set accordingly to the
   * sample rate of the source audio.
   *
   * <p>API endpoint:
   * https://bitmovin.com/docs/encoding/api-reference/sections/configurations#/Encoding/PostEncodingConfigurationsAudioAc3
   */
  private static Ac3AudioConfiguration createAc3AudioConfig() throws BitmovinException {
    Ac3AudioConfiguration config = new Ac3AudioConfiguration();
    config.setName("AC3 128 kbit/s");
    config.setBitrate(128_000L);

    return bitmovinApi.encoding.configurations.audio.ac3.create(config);
  }

  /**
   * Creates an MP4 muxing.
   *
   * <p>API endpoint:
   * https://bitmovin.com/docs/encoding/api-reference/sections/encodings#/Encoding/PostEncodingEncodingsMuxingsMp4ByEncodingId
   *
   * @param encoding The encoding to add the muxing to
   * @param output The output that should be used for the muxing to write the segments to
   * @param outputPath The output path where the fragments will be written to
   * @param streams A list of streams to be added to the muxing
   * @param fileName The name of the file that will be written to the output
   */
  private static Mp4Muxing createMp4Muxing(
      Encoding encoding, Output output, String outputPath, List<Stream> streams, String fileName)
      throws BitmovinException {
    Mp4Muxing muxing = new Mp4Muxing();
    muxing.addOutputsItem(buildEncodingOutput(output, outputPath));
    muxing.setFilename(fileName);

    for (Stream stream : streams) {
      MuxingStream muxingStream = new MuxingStream();
      muxingStream.setStreamId(stream.getId());
      muxing.addStreamsItem(muxingStream);
    }

    return bitmovinApi.encoding.encodings.muxings.mp4.create(encoding.getId(), muxing);
  }

  /**
   * Creates a progressive TS muxing.
   *
   * <p>API endpoint:
   * https://bitmovin.com/docs/encoding/api-reference/sections/encodings#/Encoding/PostEncodingEncodingsMuxingsTsByEncodingId
   *
   * @param encoding The encoding to add the muxing to
   * @param output The output that should be used for the muxing to write the segments to
   * @param outputPath The output path where the fragments will be written to
   * @param streams A list of streams to be added to the muxing
   * @param fileName The name of the file that will be written to the output
   */
  private static ProgressiveTsMuxing createProgressiveTsMuxing(
      Encoding encoding, Output output, String outputPath, List<Stream> streams, String fileName)
      throws BitmovinException {
    ProgressiveTsMuxing muxing = new ProgressiveTsMuxing();
    muxing.addOutputsItem(buildEncodingOutput(output, outputPath));
    muxing.setFilename(fileName);

    for (Stream stream : streams) {
      MuxingStream muxingStream = new MuxingStream();
      muxingStream.setStreamId(stream.getId());
      muxing.addStreamsItem(muxingStream);
    }

    return bitmovinApi.encoding.encodings.muxings.progressiveTs.create(encoding.getId(), muxing);
  }

  /**
   * Builds an EncodingOutput object which defines where the output content (e.g. of a muxing) will
   * be written to. Public read permissions will be set for the files written, so they can be
   * accessed easily via HTTP.
   *
   * @param output The output resource to be used by the EncodingOutput
   * @param outputPath The path where the content will be written to
   */
  private static EncodingOutput buildEncodingOutput(Output output, String outputPath) {
    AclEntry aclEntry = new AclEntry();
    aclEntry.setPermission(AclPermission.PUBLIC_READ);

    EncodingOutput encodingOutput = new EncodingOutput();
    encodingOutput.setOutputPath(buildAbsolutePath(outputPath));
    encodingOutput.setOutputId(output.getId());
    encodingOutput.addAclItem(aclEntry);
    return encodingOutput;
  }

  /**
   * Builds an absolute path by concatenating the S3_OUTPUT_BASE_PATH configuration parameter, the
   * name of this example class and the given relative path
   *
   * <p>e.g.: /s3/base/path/ClassName/relative/path
   *
   * @param relativePath The relative path that is concatenated
   * @return The absolute path
   */
  public static String buildAbsolutePath(String relativePath) {
    String className = MultiCodecEncoding.class.getSimpleName();
    return Paths.get(configProvider.getS3OutputBasePath(), className, relativePath).toString();
  }

  /**
   * Starts the actual encoding process and periodically polls its status until it reaches a final
   * state
   *
   * <p>API endpoints:
   * https://bitmovin.com/docs/encoding/api-reference/all#/Encoding/PostEncodingEncodingsStartByEncodingId
   * https://bitmovin.com/docs/encoding/api-reference/sections/encodings#/Encoding/GetEncodingEncodingsStatusByEncodingId
   *
   * <p>Please note that you can also use our webhooks API instead of polling the status. For more
   * information consult the API spec:
   * https://bitmovin.com/docs/encoding/api-reference/sections/notifications-webhooks
   *
   * @param encoding The encoding to be started
   */
  private static void executeEncoding(Encoding encoding)
      throws InterruptedException, BitmovinException {
    bitmovinApi.encoding.encodings.start(encoding.getId(), new StartEncodingRequest());

    Task task;
    do {
      Thread.sleep(5000);
      task = bitmovinApi.encoding.encodings.status(encoding.getId());
      logger.info("encoding status is {} (progress: {} %)", task.getStatus(), task.getProgress());
    } while (task.getStatus() != Status.FINISHED && task.getStatus() != Status.ERROR);

    if (task.getStatus() == Status.ERROR) {
      logTaskErrors(task);
      throw new RuntimeException("Encoding failed");
    }
    logger.info("encoding finished successfully");
  }

  private static void logTaskErrors(Task task) {
    task.getMessages().stream()
        .filter(msg -> msg.getType() == MessageType.ERROR)
        .forEach(msg -> logger.error(msg.getText()));
  }
}
