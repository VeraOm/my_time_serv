#from __future__ import print_function

import argparse
import datetime


def create_task(payload=None, in_seconds=None):
    # [START cloud_tasks_appengine_create_task]
    """Create a task for a given queue with an arbitrary payload."""

    from google.cloud import tasks_v2
    from google.protobuf import timestamp_pb2

    # Create a client.
    client = tasks_v2.CloudTasksClient()

    project = 'quickstart-1574153168977'
    queue = 'MyServQ'
    location = 'europe-west2'

    # Construct the fully qualified queue name.
    parent = client.queue_path(project, location, queue)

    # Construct the request body.
    task = {
            'app_engine_http_request': {  # Specify the type of request.
                'http_method': 'POST',
                'relative_uri': '/q/send_email'
            }
    }
    if payload is not None:
        # The API expects a payload of type bytes.
#        converted_payload = payload.encode()
        with open(r"d:\Temp\rawplaintext.txt", "r") as tfile:
            templ=tfile.read()
        converted_payload = templ.encode()

        # Add the payload to the request.
        task['app_engine_http_request']['body'] = converted_payload

    if in_seconds is not None:
        # Convert "seconds from now" into an rfc3339 datetime string.
        d = datetime.datetime.utcnow() + datetime.timedelta(seconds=in_seconds)

        # Create Timestamp protobuf.
        timestamp = timestamp_pb2.Timestamp()
        timestamp.FromDatetime(d)

        # Add the timestamp to the tasks.
        task['schedule_time'] = timestamp

    # Use the client to build and send the task.
    response = client.create_task(parent, task)

    print('Created task {}'.format(response.name))
    return response
# [END cloud_tasks_appengine_create_task]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=create_task.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument(
        '--project',
        help='Project of the queue to add the task to.',
#        required=True,
    )

    parser.add_argument(
        '--queue',
        help='ID (short name) of the queue to add the task to.',
#        required=True,
    )

    parser.add_argument(
        '--location',
        help='Location of the queue to add the task to.',
#        required=True,
    )

    parser.add_argument(
        '--payload',
        help='Optional payload to attach to the push queue.'
    )

    parser.add_argument(
        '--in_seconds', type=int,
        help='The number of seconds from now to schedule task attempt.'
    )

    args = parser.parse_args()

    create_task(args.payload, args.in_seconds)
