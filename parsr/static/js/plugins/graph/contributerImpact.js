ns("plugins.graph");

(function() {

    analyzr.plugins.graph.ContributerImpact = analyzr.plugins.graph.Graph.extend({

        init: function(target, attrs) {
            attrs = attrs || {};

            attrs.noFilter = attrs.noFilter || true;
            attrs.title = attrs.title || "Contributor Impact";

            this._super("impact", target, attrs);
        },

        prepareScale: function() {
            this.scale = {
                x: d3.scale.linear().range([0, this.getInnerWidth()]),
                y: d3.scale.linear().range([this.getInnerHeight(), 0])
            };

            return this.scale;
        },

        getMinValue: function() {
            return 0;
        },

        getMaxValue: function(d) {
            return d.count;
        },

        updateXScale: function(svg, info) {
            this.scale.x.domain([0, info.authorCount]);
        },

        handleMouseEnter: function(element, data) {
            var mouse = d3.mouse(element);
            var x = mouse[0];

            var position = Math.floor(this.scale.x.invert(x));
            var author = data[position];

            var that = this;

            $(element).qtip({
                content: {
                    text: function(event, api) {
                        analyzr.core.data.get(author.href + "?branch=" + that.dom.data("branch"), {
                            success: function(data) {
                                var content = data.rep.name +
                                    "<table>" +
                                        "<tbody>" +
                                            "<tr>" +
                                                "<td>" + data.rep.revisions.all + "</td>" +
                                                "<td>Overall commits</td>" +
                                            "</tr>" +
                                            "<tr>" +
                                                "<td>" + data.rep.revisions.currentPeriod + "</td>" +
                                                "<td>Commits in current period</td>" +
                                            "</tr>" +
                                        "</tbody>" +
                                    "</table>";

                                api.set("content.text", content);
                            }
                        });

                        return "Loading...";
                    }
                },
                position: {
                    my: "top center",
                    at: "bottom center",
                    adjust: {
                        y: 10
                    }
                },
                style: {
                    classes: "qtip-dark qtip-tipsy qtip-shadow",
                    tip: "bottomMiddle"
                }
            });
        },

        handleData: function(svg, response) {
            var data = [];

            $.each(response.data, function(index) {
                data.push({
                    href: this.href,
                    position: index,
                    value: this.count
                });
            });

            var that = this;

            var line = d3.svg.line()
                .interpolate("basis")
                .x(function(d) {
                    var offset = ((that.getInnerWidth() / data.length) / 2);
                    var position = that.scale.x(d.position);

                    return Math.max(0, Math.min(position, position - offset));
                })
                .y(function(d) {
                    return that.scale.y(d.value);
                });

            svg.append("clipPath")
                .attr("id", "clip")
                .append("rect")
                    .attr("width", this.getInnerWidth())
                    .attr("height", this.getInnerHeight());

            svg.selectAll(".y.axis")
                .call(this.axis.y);

            svg.selectAll(".bar")
                .data(data)
                .enter().append("rect")
                .attr("class", "bar")
                .attr("x", function(d) {
                    return that.scale.x(d.position);
                })
                .attr("width", that.getInnerWidth() / data.length)
                .attr("y", function(d) {
                    return that.scale.y(d.value);
                })
                .attr("height", function(d) {
                    return that.getInnerHeight() - that.scale.y(d.value);
                });

            svg.append("path")
                .datum(data)
                .attr("class", "curve")
                .attr("clip-path", "url(#clip)")
                .attr("d", line);

            svg.selectAll(".bar")
                .on("mouseenter", function() {
                    that.handleMouseEnter(this, data);
                });
        }

    });

}());
