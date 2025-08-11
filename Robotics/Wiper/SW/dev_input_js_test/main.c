#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>
#include <linux/joystick.h>
#include <sys/ioctl.h>

#include <time.h>


struct timespec diff_timespec(const struct timespec *time1, const struct timespec *time0) {
	struct timespec diff;

	// Calculate the difference in seconds
	diff.tv_sec = time1->tv_sec - time0->tv_sec;

	// Calculate the difference in nanoseconds
	diff.tv_nsec = time1->tv_nsec - time0->tv_nsec;

	// Handle cases where nanoseconds become negative due to borrowing from seconds
	if (diff.tv_nsec < 0) {
		diff.tv_sec--; // Decrement seconds
		diff.tv_nsec += 1000000000; // Add one billion nanoseconds (1 second)
	}

	return diff;
}

int main() {
	int js_fd;
	struct js_event js_event_data;

	int num_of_axes = 0;
	int num_of_buttons = 0;

	struct timespec t_curr;
	struct timespec t_prev;

	// Open the joystick device file in read-only mode
	js_fd = open("/dev/input/js0", O_RDONLY);
	if (js_fd == -1) {
		perror("Error opening joystick device");
		return 1;
	}

	ioctl(js_fd, JSIOCGAXES, &num_of_axes);
	ioctl(js_fd, JSIOCGBUTTONS, &num_of_buttons);

	printf("Number of axes: %d\n", num_of_axes);
	printf("Number of buttons: %d\n", num_of_buttons);
	
	clock_gettime(CLOCK_MONOTONIC, &t_prev);

	// Continuously read joystick events
	while (1) {
		if (read(js_fd, &js_event_data, sizeof(struct js_event)) == sizeof(struct js_event)) {
			clock_gettime(CLOCK_MONOTONIC, &t_curr);

			struct timespec T_delta = diff_timespec(&t_curr, &t_prev);
			double delta = T_delta.tv_sec + T_delta.tv_nsec*1e-9;
			double rate = 1.0/delta;
			printf("delta = %lf ms, rate = %lfHz\n", delta*1e3, rate);
			t_prev = t_curr;


			// Process the event based on its type
			if (js_event_data.type & JS_EVENT_BUTTON) {
				printf("Button %d %s (value: %d)\n",
					   js_event_data.number,
					   (js_event_data.value == 0) ? "released" : "pressed",
					   js_event_data.value);
			} else if (js_event_data.type & JS_EVENT_AXIS) {
				printf("Axis %d moved (value: %d)\n",
					   js_event_data.number,
					   js_event_data.value);
			} else if (js_event_data.type & JS_EVENT_INIT) {
				printf("Initial state event (type: %d, number: %d, value: %d)\n",
					   js_event_data.type, js_event_data.number, js_event_data.value);
			}
		} else {
			perror("Error reading joystick event");
			break;
		}
	}

	// Close the device file
	close(js_fd);
	return 0;
}