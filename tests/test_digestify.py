# import asyncio

# from digestify_api.stories.digestify import Digestify, Topic


# async def main() -> None:
#     topic = Topic(
#         name="H3 Podcast",
#         description=(
#             "A podcast hosted by Ethan Klein. "
#             "Main channel is called 'H3 Podcast' on YouTube."
#         ),
#     )

#     digestify = Digestify()

#     digest = await digestify.get_stories(topic)
#     print(digest.model_dump_json(indent=4))


# if __name__ == "__main__":
#     asyncio.run(main())
