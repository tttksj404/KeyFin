package com.finset.key_fin.global.config;

import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.ScheduledAnnotationBeanPostProcessor;
import org.springframework.scheduling.config.CronTask;

import com.finset.key_fin.support.SpringIntegrationTestSupport;

import static org.assertj.core.api.Assertions.assertThat;

class SchedulerCronRegistrationTest extends SpringIntegrationTestSupport {

	@Autowired
	private ScheduledAnnotationBeanPostProcessor scheduledTasks;

	@Test
	void 배치_다섯_개가_속성의_크론으로_등록된다() {
		List<String> expressions = scheduledTasks.getScheduledTasks().stream()
				.map(task -> task.getTask())
				.filter(CronTask.class::isInstance)
				.map(task -> ((CronTask) task).getExpression())
				.toList();

		assertThat(expressions).containsExactlyInAnyOrder(
				"0 * * * * *", "0 0 21 * * *", "0 0 8,17 * * *", "0 30 8 * * *", "0 0/30 * * * *");
	}
}
