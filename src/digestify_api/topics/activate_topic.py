# @router.post("/activate", status_code=200)
# async def activate_topic(
#     auth: Annotated[schemas.auth.Auth, Depends(database.auth.get_auth)],
#     db_manager: Annotated[database.db.DBManager, Depends(database.db.get_db_manager)],
#     topic_id: UUID,
# ) -> None:
#     if auth.is_anonymous:
#         raise exceptions.auth.InsufficientPermissions()

#     async with db_manager.get_connection() as connection:
#         now = datetime.now(timezone.utc)

#         user = await queries.users.get(connection, auth.id, lock=True)
#         if user is None:
#             raise exceptions.users.UserNotFound()

#         topic = await queries.topics.get(connection, topic_id, lock=True)
#         if topic is None or topic.user_id != auth.id:
#             raise exceptions.topics.TopicNotFound()

#         if topic.is_active:
#             return

#         if user.tier is schemas.users.UserTier.FREE:
#             raise exceptions.topics.TopicLimitExceeded(
#                 detail=(
#                     "Free tier users cannot activate topics. "
#                     "Please upgrade your subscription to activate topics."
#                 )
#             )

#         if (
#             user.active_topics_count >= 5
#             and user.tier is schemas.users.UserTier.PREMIUM
#         ):
#             raise exceptions.topics.TopicLimitExceeded(
#                 detail=(
#                     "Premium tier users can have up to 5 active topics. "
#                     "Please deactivate some topics to activate new ones."
#                 )
#             )

#         tz = ZoneInfo(topic.schedule_timezone)
#         now_in_tz = now.astimezone(tz)
#         if topic.schedule_time < now_in_tz.time():
#             schedule_date = now_in_tz.date() + timedelta(days=1)
#         else:
#             schedule_date = now_in_tz.date()
#         schedule_date = max(schedule_date, topic.schedule_date)
#         schedule = datetime.combine(schedule_date, topic.schedule_time, tzinfo=tz)

#         topic.is_active = True
#         topic.updated_at = now
#         topic.schedule_version += 1
#         topic.schedule_date = schedule_date

#         await queries.topics.update(connection, topic)
#         await queries.users.increment_active_topics_count(connection, auth.id)

#         task_paylaod = schemas.stories.FetchAndSaveStoriesTask(
#             topic_id=topic.id,
#             schedule_version=topic.schedule_version,
#             schedule_date=topic.schedule_date,
#             schedule_time=topic.schedule_time,
#             schedule_timezone=topic.schedule_timezone,
#         )
#         task = schemas.tasks.Task(
#             id=uuid4(),
#             name="fetch_and_save_stories",
#             status=schemas.tasks.TaskStatus.PENDING,
#             created_at=now,
#             updated_at=None,
#             payload=task_paylaod.model_dump_json(),
#             scheduled_at=_get_scheduled_at(schedule, now),
#             error_message=None,
#         )
#         await queries.tasks.create(connection, task)
