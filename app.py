
                    folium.CircleMarker(
                        location=[row.geometry.y, row.geometry.x],
                        radius=7,
                        color="#005A9C",
                        fill=True,
                        fill_color="#0080FF",
                        fill_opacity=0.8,
                        popup=folium.Popup(popup_html, max_width=250),
                    ).add_to(marker_cluster)

            st_folium(
                m,
                use_container_width=True,
                height=480,
                key=f"map_render_{selected_region}",
            )

    with col_table:
        st.subheader("📋 Raw ONS Indicator Table")

        display_df = gdf.drop(columns=["geometry", "areacd_clean", "latitude", "longitude"], errors="ignore")
        st.dataframe(
            display_df,
            use_container_width=True,
            height=360,
        )

        geojson_bytes = gdf.to_crs("EPSG:4326").to_json()
        st.download_button(
            label=f"📥 Export {selected_region} GeoJSON",
            data=geojson_bytes,
            file_name=f"{str(selected_region).lower().replace(' ', '_')}_ons_data.geojson",
            mime="application/geo+json",
            use_container_width=True,
        )

except Exception as e:
    st.error(f"App Execution Error: {str(e)}")
