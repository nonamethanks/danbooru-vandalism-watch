import discord
from discord import Color
from discord.types.embed import Embed
from danboorutools import logger


class Styles:
    active = discord.ButtonStyle.green
    revert = discord.ButtonStyle.grey


class PersistentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Mark handled", style=Styles.active, custom_id="persistent_view:green")
    async def green(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = interaction.message.embeds[0]  # type: ignore[union-attr, misc]

        original_label = "Mark handled"
        undo_label = "Undo mark handled"
        clicked = original_label if button.label == original_label else undo_label
        is_revert = True if button.label != original_label else False

        logger.info(
            f"Discord user #{interaction.user.name} ({interaction.user.display_name}) "
            f"clicked '{clicked}' for {interaction.message.jump_url}"  # type: ignore[union-attr]
        )

        embed = self.edit_embed(
            embed,
            is_revert,
            interaction.user,  # type: ignore[arg-type]  # I FUCKING HATE MYPY I FUCKING HATE MYPY
            default_color=Color.green(),
        )

        self.fix_buttons(button, original_label, undo_label)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Mark false positive", style=Styles.active, custom_id="persistent_view:grey")
    async def grey(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = interaction.message.embeds[0]  # type: ignore[union-attr, misc]

        original_label = "Mark false positive"
        undo_label = "Undo false positive"

        clicked = original_label if button.label == original_label else undo_label
        is_revert = True if button.label != original_label else False

        logger.info(
            f"Discord user #{interaction.user.name} ({interaction.user.display_name}) "
            f"clicked '{clicked}' for {interaction.message.jump_url}"  # type: ignore[union-attr]
        )

        embed = self.edit_embed(
            embed,
            is_revert,
            interaction.user,  # type: ignore[arg-type]  # I FUCKING HATE MYPY I FUCKING HATE MYPY
            default_color=Color.dark_grey(),
        )
        self.fix_buttons(button, original_label, undo_label)
        await interaction.response.edit_message(embed=embed, view=self)

    def edit_embed(
        self,
        embed: discord.Embed,
        is_revert: bool,
        editor: discord.Member,
        default_color: Color,
    ) -> discord.Embed:
        ####################################################################################

        embed.colour = Color.red() if is_revert else default_color

        embed_dict = embed.to_dict()
        self.toggle_field_strike(embed_dict, is_revert=is_revert)
        self.set_last_editors(embed_dict, editor)
        embed = discord.Embed.from_dict(embed_dict)

        return embed

    def fix_buttons(self, button: discord.ui.Button, original_label: str, undo_label: str):
        if button.label == original_label:
            button.label = undo_label
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
                    child.style = Styles.revert
            button.disabled = False
        else:
            button.label = original_label
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = False
                    child.style = Styles.active

    def toggle_field_strike(self, embed_dict: Embed, is_revert: bool = True) -> None:
        for field in embed_dict["fields"]:
            if field["name"] == "Last handled by":
                continue

            if is_revert:
                field["name"] = field["name"].strip("~")
                field["value"] = field["value"].strip("~")
            else:
                field["name"] = f"~~{field['name']}~~"
                field["value"] = f"~~{field['value']}~~"

    def set_last_editors(self, embed_dict: Embed, last_editor: discord.Member) -> None:
        try:
            editor_field = [f for f in embed_dict["fields"] if f["name"] == "Last handled by"][0]
        except IndexError:
            editor_field = {"name": "Last handled by", "value": f"<@{last_editor.id}>", "inline": False}
            embed_dict["fields"].append(editor_field)
        else:
            editor_field["value"] = f"<@{last_editor.id}>"
