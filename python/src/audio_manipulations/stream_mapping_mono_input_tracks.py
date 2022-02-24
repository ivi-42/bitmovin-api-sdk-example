import time
from datetime import datetime
from os import path

from bitmovin_api_sdk import AacAudioConfiguration, AclEntry, AclPermission, AudioMixChannelType, \
    AudioMixInputChannelLayout, AudioMixInputStream, AudioMixInputStreamChannel, AudioMixSourceChannelType, \
    AudioMixInputStreamSourceChannel, BitmovinApi, BitmovinApiLogger, CodecConfiguration, \
    DolbyDigitalAudioConfiguration, DolbyDigitalChannelLayout, Encoding, EncodingOutput, H264VideoConfiguration, \
    HttpInput, IngestInputStream, Input, InputStream, MessageType, Mp4Muxing, MuxingStream, Output, \
    PresetConfiguration, S3Output, Status, Stream, StreamInput, StreamMode, StreamSelectionMode, Task
from common.config_provider import ConfigProvider

"""
This example demonstrates one mechanism to create a stereo and surround audio track in the output
from multiple mono input tracks, using multiple IngestInputStreams (by position in the source),
and mapping them to output channels (by type).

<p>This example illustrates one of the use cases in the [tutorial on audio manipulations]
(https://bitmovin.com/docs/encoding/tutorials/separating-and-combining-audio-streams)

<p>The following configuration parameters are expected:

<ul>
  <li>BITMOVIN_API_KEY - Your API key for the Bitmovin API
  <li>BITMOVIN_TENANT_ORG_ID - (optional) The ID of the Organisation in which you want to perform
      the encoding.
  <li>HTTP_INPUT_HOST - The Hostname or IP address of the HTTP server hosting your input files,
      e.g.: my-storage.biz
  <li>HTTP_INPUT_FILE_PATH_MULTIPLE_MONO_AUDIO_TRACKS - the path to a file containing a video
      with multiple mono audio tracks
  <li>S3_OUTPUT_BUCKET_NAME - The name of your S3 output bucket. Example: my-bucket-name
  <li>S3_OUTPUT_ACCESS_KEY - The access key of your S3 output bucket
  <li>S3_OUTPUT_SECRET_KEY - The secret key of your S3 output bucket
  <li>S3_OUTPUT_BASE_PATH - The base path on your S3 output bucket where content will be written.
      Example: /outputs
</ul>

<p>Configuration parameters will be retrieved from these sources in the listed order:

<ol>
  <li>command line arguments (eg BITMOVIN_API_KEY=xyz)
  <li>properties file located in the root folder of the JAVA examples at ./examples.properties
      (see examples.properties.template as reference)
  <li>environment variables
  <li>properties file located in the home folder at ~/.bitmovin/examples.properties (see
      examples.properties.template as reference)
</ol>
"""

EXAMPLE_NAME = "StreamMappingMonoInputTracks-{}".format(datetime.now().isoformat(timespec='seconds'))
config_provider = ConfigProvider()
bitmovin_api = BitmovinApi(api_key=config_provider.get_bitmovin_api_key(),
                           # uncomment the following line if you are working with a multi-tenant account
                           # tenant_org_id=config_provider.get_bitmovin_tenant_org_id(),
                           logger=BitmovinApiLogger())


class ChannelMappingConfig:
    """
    Helper class representing the mapping from source channels to output channels
    """

    def __init__(self, output_channel_type, source_channel_number):
        # type: (AudioMixChannelType, int) -> None
        self._output_channel_type = output_channel_type
        self._source_channel_number = source_channel_number

    @property
    def output_channel_type(self):
        # type: () -> AudioMixChannelType
        return self._output_channel_type

    @property
    def source_channel_number(self):
        # type: () -> int
        return self._source_channel_number


def main():
    encoding = _create_encoding(
        name="Audio Mapping - Stream Mapping - Multiple Mono Tracks",
        description="Input with multiple mono tracks -> Output with stereo and surround tracks"
    )

    http_input = _create_http_input(host=config_provider.get_http_input_host())
    output = _create_s3_output(
        bucket_name=config_provider.get_s3_output_bucket_name(),
        access_key=config_provider.get_s3_output_access_key(),
        secret_key=config_provider.get_s3_output_secret_key()
    )

    h264_config = _create_h264_video_configuration()
    aac_config = _create_aac_audio_configuration()
    dd_config = _create_dd_surround_audio_configuration()

    input_file_path = config_provider.get_http_input_file_path_with_multiple_mono_audio_tracks()

    video_ingest_input_stream = _create_ingest_input_stream(
        encoding=encoding,
        input=http_input,
        input_path=input_file_path
    )

    stereo_map = [
        ChannelMappingConfig(output_channel_type=AudioMixChannelType.FRONT_LEFT, source_channel_number=0),
        ChannelMappingConfig(output_channel_type=AudioMixChannelType.FRONT_RIGHT, source_channel_number=1)
    ]
    surround_map = [
        ChannelMappingConfig(output_channel_type=AudioMixChannelType.FRONT_LEFT, source_channel_number=2),
        ChannelMappingConfig(output_channel_type=AudioMixChannelType.FRONT_RIGHT, source_channel_number=3),
        ChannelMappingConfig(output_channel_type=AudioMixChannelType.BACK_LEFT, source_channel_number=4),
        ChannelMappingConfig(output_channel_type=AudioMixChannelType.BACK_RIGHT, source_channel_number=5),
        ChannelMappingConfig(output_channel_type=AudioMixChannelType.CENTER, source_channel_number=6),
        ChannelMappingConfig(output_channel_type=AudioMixChannelType.LOW_FREQUENCY, source_channel_number=7),
    ]

    stereo_mix_input_stream = _create_audio_mix_input_stream(
        encoding=encoding,
        input=http_input,
        input_file_path=input_file_path,
        channel_layout=AudioMixInputChannelLayout.CL_STEREO,
        mapping_configs=stereo_map
    )

    surround_mix_input_stream = _create_audio_mix_input_stream(
        encoding=encoding,
        input=http_input,
        input_file_path=input_file_path,
        channel_layout=AudioMixInputChannelLayout.CL_5_1_BACK,
        mapping_configs=surround_map
    )

    video_stream = _create_stream(
        encoding=encoding,
        input_stream=video_ingest_input_stream,
        codec_configuration=h264_config
    )
    audio_stream1 = _create_stream(
        encoding=encoding,
        input_stream=stereo_mix_input_stream,
        codec_configuration=aac_config
    )
    audio_stream2 = _create_stream(
        encoding=encoding,
        input_stream=surround_mix_input_stream,
        codec_configuration=dd_config
    )

    _create_mp4_muxing(
        encoding=encoding,
        output=output,
        output_path="/",
        streams=[video_stream, audio_stream1, audio_stream2],
        file_name="stereo-and-surround-tracks-mapped.mp4"
    )

    _execute_encoding(encoding=encoding)


def _execute_encoding(encoding):
    # type: (Encoding) -> None
    """
    Starts the actual encoding process and periodically polls its status until it reaches a final state

    <p>API endpoints:
    https://bitmovin.com/docs/encoding/api-reference/all#/Encoding/PostEncodingEncodingsStartByEncodingId
    https://bitmovin.com/docs/encoding/api-reference/sections/encodings#/Encoding/GetEncodingEncodingsStatusByEncodingId

    <p>Please note that you can also use our webhooks API instead of polling the status. For more
    information consult the API spec:
    https://bitmovin.com/docs/encoding/api-reference/sections/notifications-webhooks

    :param encoding: The encoding to be started
    """
    bitmovin_api.encoding.encodings.start(encoding_id=encoding.id)

    task = _wait_for_enoding_to_finish(encoding_id=encoding.id)

    while task.status is not Status.FINISHED and task.status is not Status.ERROR:
        task = _wait_for_enoding_to_finish(encoding_id=encoding.id)

    if task.status is Status.ERROR:
        _log_task_errors(task=task)
        raise Exception("Encoding failed")

    print("Encoding finished successfully")


def _wait_for_enoding_to_finish(encoding_id):
    # type: (str) -> Task
    """
    Waits five second and retrieves afterwards the status of the given encoding id

    :param encoding_id: The encoding which should be checked
    """

    time.sleep(5)
    task = bitmovin_api.encoding.encodings.status(encoding_id=encoding_id)
    print("Encoding status is {} (progress: {} %)".format(task.status, task.progress))
    return task


def _create_encoding(name, description):
    # type: (str, str) -> Encoding
    """
    Creates an Encoding object. This is the base object to configure your encoding.

    API endpoint:
    https://bitmovin.com/docs/encoding/api-reference/sections/encodings#/Encoding/PostEncodingEncodings

    :param name: A name that will help you identify the encoding in our dashboard (required)
    :param description: A description of the encoding (optional)
    """

    encoding = Encoding(
        name=name,
        description=description
    )
    return bitmovin_api.encoding.encodings.create(encoding=encoding)


def _create_http_input(host):
    # type: (str) -> HttpInput
    """
    Creates a resource representing an HTTP server providing the input files. For alternative input methods see
    <a href="https://bitmovin.com/docs/encoding/articles/supported-input-output-storages">
    list of supported input and output storages</a>

    For reasons of simplicity, a new input resource is created on each execution of this
    example. In production use, this method should be replaced by a
    <a href="https://bitmovin.com/docs/encoding/api-reference/sections/inputs#/Encoding/GetEncodingInputsHttpByInputId">
    get call</a> to retrieve an existing resource.

    API endpoint:
        https://bitmovin.com/docs/encoding/api-reference/sections/inputs#/Encoding/PostEncodingInputsHttp

    :param host: The hostname or IP address of the HTTP server e.g.: my-storage.biz
    """
    http_input = HttpInput(host=host)

    return bitmovin_api.encoding.inputs.http.create(http_input=http_input)


def _create_s3_output(bucket_name, access_key, secret_key):
    # type: (str, str, str) -> S3Output
    """
    Creates a resource representing an AWS S3 cloud storage bucket to which generated content will be transferred.
    For alternative output methods see
    <a href="https://bitmovin.com/docs/encoding/articles/supported-input-output-storages">
    list of supported input and output storages</a>

    <p>The provided credentials need to allow <i>read</i>, <i>write</i> and <i>list</i> operations.
    <i>delete</i> should also be granted to allow overwriting of existings files. See <a
    href="https://bitmovin.com/docs/encoding/faqs/how-do-i-create-a-aws-s3-bucket-which-can-be-used-as-output-location">
    creating an S3 bucket and setting permissions</a> for further information

    <p>For reasons of simplicity, a new output resource is created on each execution of this
    example. In production use, this method should be replaced by a
    <a href="https://bitmovin.com/docs/encoding/api-reference/sections/outputs#/Encoding/GetEncodingOutputsS3">
    get call</a> retrieving an existing resource.

    <p>API endpoint:
    https://bitmovin.com/docs/encoding/api-reference/sections/outputs#/Encoding/PostEncodingOutputsS3

    :param bucket_name: The name of the S3 bucket
    :param access_key: The access key of your S3 account
    :param secret_key: The secret key of your S3 account
    """

    s3_output = S3Output(
        bucket_name=bucket_name,
        access_key=access_key,
        secret_key=secret_key
    )

    return bitmovin_api.encoding.outputs.s3.create(s3_output=s3_output)


def _create_ingest_input_stream(encoding, input, input_path):
    # type: (Encoding, Input, str) -> IngestInputStream
    """
    Creates an IngestInputStream and adds it to an encoding

    <p>The IngestInputStream is used to define where a file to read a stream from is located

    <p>API endpoint:
    https://bitmovin.com/docs/encoding/api-reference/sections/encodings#/Encoding/PostEncodingEncodingsInputStreamsIngestByEncodingId

    :param encoding: The encoding to which the stream will be added
    :param input: The input resource providing the input file
    :param input_path: The path to the input file
    """

    ingest_input_stream = IngestInputStream(
        input_id=input.id,
        input_path=input_path,
        selection_mode=StreamSelectionMode.AUTO
    )

    return bitmovin_api.encoding.encodings.input_streams.ingest.create(
        encoding_id=encoding.id,
        ingest_input_stream=ingest_input_stream
    )


def _create_ingest_input_stream_for_audio_track(encoding, input, input_path, position):
    # type: (Encoding, Input, str, int) -> IngestInputStream
    """
    Creates an IngestInputStream to select a specific audio strack in the input, and adds it to an
    encoding

    <p>The IngestInputStream is used to define where a file to read a stream from is located

    <p>API endpoint:
    https://bitmovin.com/docs/encoding/api-reference/sections/encodings#/Encoding/PostEncodingEncodingsInputStreamsIngestByEncodingId

    :param encoding: The encoding to which the stream will be added
    :param input: The input resource providing the input file
    :param input_path: The path to the input file
    :param position: The relative position of the audio track to select in the input file
    """

    ingest_input_stream = IngestInputStream(
        input_id=input.id,
        input_path=input_path,
        selection_mode=StreamSelectionMode.AUDIO_RELATIVE,
        position=position
    )

    return bitmovin_api.encoding.encodings.input_streams.ingest.create(
        encoding_id=encoding.id,
        ingest_input_stream=ingest_input_stream
    )


def _create_audio_mix_input_stream(encoding, input, input_file_path, channel_layout, mapping_configs):
    # type: (Encoding, Input, str, AudioMixInputChannelLayout, list) -> AudioMixInputStream
    audio_mix_input_stream = AudioMixInputStream(
        channel_layout=channel_layout
    )

    for mapping_config in mapping_configs:
        audio_ingest_input_stream = _create_ingest_input_stream_for_audio_track(
            encoding=encoding,
            input=input,
            input_path=input_file_path,
            position=mapping_config.source_channel_number
        )

        output_channel = AudioMixInputStreamChannel(
            input_stream_id=audio_ingest_input_stream.id,
            output_channel_type=mapping_config.output_channel_type
        )

        source_channel = AudioMixInputStreamSourceChannel(
            type_=AudioMixSourceChannelType.CHANNEL_NUMBER,
            channel_number=0
        )

        output_channel.source_channels.append(source_channel)
        audio_mix_input_stream.audio_mix_channels.append(output_channel)

    return bitmovin_api.encoding.encodings.input_streams.audio_mix.create(
        encoding_id=encoding.id,
        audio_mix_input_stream=audio_mix_input_stream
    )


def _create_h264_video_configuration():
    # type: () -> H264VideoConfiguration
    """
    Creates a configuration for the H.264 video codec to be applied to video streams.

    <p>The output resolution is defined by setting the height to 1080 pixels. Width will be
    determined automatically to maintain the aspect ratio of your input video.

    <p>To keep things simple, we use a quality-optimized VoD preset configuration, which will apply
    proven settings for the codec. See <a
    href="https://bitmovin.com/docs/encoding/tutorials/how-to-optimize-your-h264-codec-configuration-for-different-use-cases">How
    to optimize your H264 codec configuration for different use-cases</a> for alternative presets.

    <p>API endpoint:
    https://bitmovin.com/docs/encoding/api-reference/sections/configurations#/Encoding/PostEncodingConfigurationsVideoH264
    """

    config = H264VideoConfiguration(
        name="H.264 1080p @ 1.5 Mbit/S",
        height=1080,
        bitrate=1500000,
        preset_configuration=PresetConfiguration.VOD_STANDARD
    )

    return bitmovin_api.encoding.configurations.video.h264.create(h264_video_configuration=config)


def _create_stream(encoding, input_stream, codec_configuration):
    # type: (Encoding, InputStream, CodecConfiguration) -> Stream
    """
    Adds a video or audio stream to an encoding

    <p>API endpoint:
    https://bitmovin.com/docs/encoding/api-reference/sections/encodings#/Encoding/PostEncodingEncodingsStreamsByEncodingId

    :param encoding: The encoding to which the stream will be added
    :param input_stream: The inputStream resource providing the input file
    :param: codec_configuration: The codec configuration to be applied to the stream
    """

    stream_input = StreamInput(
        input_stream_id=input_stream.id
    )

    stream = Stream(
        input_streams=[stream_input],
        codec_config_id=codec_configuration.id,
        mode=StreamMode.STANDARD
    )

    return bitmovin_api.encoding.encodings.streams.create(encoding_id=encoding.id, stream=stream)


def _create_aac_audio_configuration():
    # type: () -> AacAudioConfiguration
    """
    Creates a configuration for the AAC audio codec to be applied to audio streams.

    <p>API endpoint:
    https://bitmovin.com/docs/encoding/api-reference/sections/configurations#/Encoding/PostEncodingConfigurationsAudioAac
    """

    config = AacAudioConfiguration(
        name="AAC Audio @ 128 kbit/s",
        bitrate=128000
    )

    return bitmovin_api.encoding.configurations.audio.aac.create(aac_audio_configuration=config)


def _create_dd_surround_audio_configuration():
    # type: () -> DolbyDigitalAudioConfiguration
    """
    Creates a Dolby Digital audio configuration.

    <p>API endpoint:
    https://bitmovin.com/docs/encoding/api-reference/sections/configurations#/Encoding/PostEncodingConfigurationsAudioDD
    """
    config = DolbyDigitalAudioConfiguration(
        name="Dolby Digital Channel Layout 5.1",
        bitrate=256000,
        channel_layout=DolbyDigitalChannelLayout.CL_5_1
    )

    return bitmovin_api.encoding.configurations.audio.dolby_digital.create(dolby_digital_audio_configuration=config)


def _create_mp4_muxing(encoding, output, output_path, streams, file_name):
    # type: (Encoding, Output, str, list[Stream], str) -> Mp4Muxing
    """
    Creates a fragmented MP4 muxing. This will generate segments with a given segment length for
    adaptive streaming.

    <p>API endpoint:
    https://bitmovin.com/docs/encoding/api-reference/all#/Encoding/PostEncodingEncodingsMuxingsFmp4ByEncodingId

    :param encoding: The encoding where to add the muxing to
    :param output: The output that should be used for the muxing to write the segments to
    :param output_path: The output path where the fragmented segments will be written to
    :param streams: The stream that is associated with the muxing
    :param file_name: The name of the file that will be written to the output
    """

    muxing = Mp4Muxing(
        outputs=[_build_encoding_output(output=output, output_path=output_path)],
        filename=file_name
    )

    for stream in streams:
        muxing_stream = MuxingStream(stream_id=stream.id)
        muxing.streams.append(muxing_stream)

    return bitmovin_api.encoding.encodings.muxings.mp4.create(encoding_id=encoding.id,
                                                              mp4_muxing=muxing)


def _build_encoding_output(output, output_path):
    # type: (Output, str) -> EncodingOutput
    """
    Builds an EncodingOutput object which defines where the output content (e.g. of a muxing) will be written to.
    Public read permissions will be set for the files written, so they can be accessed easily via HTTP.

    :param output: The output resource to be used by the EncodingOutput
    :param output_path: The path where the content will be written to
    """

    acl_entry = AclEntry(
        permission=AclPermission.PUBLIC_READ
    )

    return EncodingOutput(
        output_path=_build_absolute_path(relative_path=output_path),
        output_id=output.id,
        acl=[acl_entry]
    )


def _build_absolute_path(relative_path):
    # type: (str) -> str
    """
    Builds an absolute path by concatenating the S3_OUTPUT_BASE_PATH configuration parameter, the
    name of this example and the given relative path

    <p>e.g.: /s3/base/path/exampleName/relative/path

    :param relative_path: The relative path that is concatenated
    """

    return path.join(config_provider.get_s3_output_base_path(), EXAMPLE_NAME, relative_path)


def _log_task_errors(task):
    # type: (Task) -> None
    """
    Logs all task errors

    :param task: The task with the error messages
    """

    if task is None:
        return

    filtered = [x for x in task.messages if x.type is MessageType.ERROR]

    for message in filtered:
        print(message.text)


main()
