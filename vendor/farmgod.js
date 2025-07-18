// ScriptAPI.register('FarmGod', true, 'Warre', 'nl.tribalwars@coma.innogames.de');
;(function(window, $, document, undefined) {
  // prevent double‐loading
  if (window.FarmGod && window.FarmGod._initialized) {
    return;
  }
  window.FarmGod = window.FarmGod || {};
  window.FarmGod._initialized = true;
    
const mobileCheck = window.mobile;
const version = 2.1;
const farmGodKey = `farmGod_${version}_options`;

window.FarmGod = {};
window.FarmGod.Library = (function () {
    /**** TribalWarsLibrary.js ****/
    if (typeof window.twLib === 'undefined') {
        window.twLib = {
            queues: null,
            init: function () {
                if (this.queues === null) {
                    this.queues = this.queueLib.createQueues(5);
                }
            },
            queueLib: {
                maxAttempts: 3,
                Item: function (action, arg, promise = null) {
                    this.action = action;
                    this.arguments = arg;
                    this.promise = promise;
                    this.attempts = 0;
                },
                Queue: function () {
                    this.list = [];
                    this.working = false;
                    this.length = 0;

                    this.doNext = function () {
                        let item = this.dequeue();
                        let self = this;

                        if (item.action == 'openWindow') {
                            window.open(...item.arguments).addEventListener('DOMContentLoaded', function () {
                                self.start();
                            });
                        } else {
                            $[item.action](...item.arguments).done(function () {
                                item.promise.resolve.apply(null, arguments);
                                self.start();
                            }).fail(function () {
                                item.attempts += 1;
                                if (item.attempts < twLib.queueLib.maxAttempts) {
                                    self.enqueue(item, true);
                                } else {
                                    item.promise.reject.apply(null, arguments);
                                }

                                self.start();
                            });
                        }
                    };

                    this.start = function () {
                        if (this.length) {
                            this.working = true;
                            this.doNext();
                        } else {
                            this.working = false;
                        }
                    };

                    this.dequeue = function () {
                        this.length -= 1;
                        return this.list.shift();
                    };

                    this.enqueue = function (item, front = false) {
                        (front) ? this.list.unshift(item) : this.list.push(item);
                        this.length += 1;

                        if (!this.working) {
                            this.start();
                        }
                    };
                },
                createQueues: function (amount) {
                    let arr = [];

                    for (let i = 0; i < amount; i++) {
                        arr[i] = new twLib.queueLib.Queue();
                    }

                    return arr;
                },
                addItem: function (item) {
                    let leastBusyQueue = twLib.queues.map(q => q.length).reduce((next, curr) => (curr < next) ? curr : next, 0);
                    twLib.queues[leastBusyQueue].enqueue(item);
                },
                orchestrator: function (type, arg) {
                    let promise = $.Deferred();
                    let item = new twLib.queueLib.Item(type, arg, promise);

                    twLib.queueLib.addItem(item);

                    return promise;
                }
            },
            ajax: function () {
                return twLib.queueLib.orchestrator('ajax', arguments);
            },
            get: function () {
                return twLib.queueLib.orchestrator('get', arguments);
            },
            post: function () {
                return twLib.queueLib.orchestrator('post', arguments);
            },
            openWindow: function () {
                let item = new twLib.queueLib.Item('openWindow', arguments);

                twLib.queueLib.addItem(item);
            }
        };

        twLib.init();
    }


    /**** Script Library ****/
    const setUnitSpeeds = function () {
        let unitSpeeds = {};

        $.when($.get('/interface.php?func=get_unit_info')).then((xml) => {
            $(xml).find('config').children().map((i, el) => {
                unitSpeeds[$(el).prop('nodeName')] = $(el).find('speed').text().toNumber();
            });

            localStorage.setItem('FarmGod_unitSpeeds', JSON.stringify(unitSpeeds));
        });
    };

    const getUnitSpeeds = function () {
        return JSON.parse(localStorage.getItem('FarmGod_unitSpeeds')) || false;
    };

    if (!getUnitSpeeds()) setUnitSpeeds();

    const determineNextPage = function (page, $html) {
        let villageLength = ($html.find('#scavenge_mass_screen').length > 0) ? $html.find('tr[id*="scavenge_village"]').length : $html.find('tr.row_a, tr.row_ax, tr.row_b, tr.row_bx').length;
        let navSelect = $html.find('.paged-nav-item').first().closest('td').find('select').first();
        let navLength = ($html.find('#am_widget_Farm').length > 0) ? $html.find('#plunder_list_nav').first().find('a.paged-nav-item').length : ((navSelect.length > 0) ? navSelect.find('option').length - 1 : $html.find('.paged-nav-item').not('[href*="page=-1"]').length);
        let pageSize = ($('#mobileHeader').length > 0) ? 10 : parseInt($html.find('input[name="page_size"]').val());

        if (page == -1 && villageLength == 1000) {
            return Math.floor(1000 / pageSize);
        } else if (page < navLength) {
            return page + 1;
        }

        return false;
    };

    const processPage = function (url, page, wrapFn) {
        let pageText = (url.match('am_farm')) ? `&Farm_page=${page}` : `&page=${page}`;

        return twLib.ajax({
            url: url + pageText
        }).then((html) => {
            return wrapFn(page, $(html));
        });
    };

    const loadAllFromOverview = async (mode, groupId = 0, overviewType = "all", returnType, additionalData = {}) => {
        try {
            let checkedPages = false;
            let shouldConsiderPages = false;

            const getOverviewHtml = async (page) => {
                return await twLib.get(`${game_data.link_base_pure}overview_villages&mode=${mode}&group=${groupId}&page=${page}&type=${overviewType}`);
            };

            const loadOverviewPage = async (page = -1) => {
                // Added this to be able to set the commands filter
                if (mode === "commands" && !checkedPages) {
                    try {
                        await twLib.post(`${game_data.link_base_pure}overview_villages&mode=commands&action=save_filters`, {
                            "filters[start_comment]": additionalData?.["start_comment"] ?? "",
                            "filters[origin_name]": additionalData?.["origin_name"] ?? "",
                            "filter_icon_radio": additionalData?.["filter_icon_radio"] ?? 0,
                            "expression": additionalData?.["expression"] ?? "AND",
                            "h": game_data.csrf
                        });
                    } catch (error) {
                        if (error.status !== 302 && error.status !== 0) {
                            throw error;
                        }
                    }
                }

                const html = await getOverviewHtml(page);
                if (!checkedPages) {
                    checkedPages = true;

                    if (!mobileCheck) {
                        const playerVillages = parseInt(game_data.player.villages);
                        const pageSize = parseInt($(`[name="page_size"]`, html)?.val()?.trim() ?? 10);
                        const tableRows = $(`.overview_table tr[class*="row_"]`, html).length;

                        shouldConsiderPages = (playerVillages > 1000 || tableRows >= 1000);

                        if (pageSize !== 1000 && shouldConsiderPages) {
                            await twLib.post(`${game_data.link_base_pure}overview_villages&mode=${mode}&action=change_page_size&type=all`, `page_size=1000&h=${game_data.csrf}`);
                            return await getOverviewHtml(page);
                        }
                    } else {
                        shouldConsiderPages = true;
                    }
                }

                return html;
            }

            const getVillages = (html) => {
                const table = $('.small, .overview_table, #commands_table, .overview-container', html);
                const villages = $(`[class*="row_"], .overview-container-item`, table).get();

                if (returnType === 'coord') {
                    if (mobileCheck) {
                        return villages.map(village => $(village).prev().find(`th:first a:first`).text().trim().toCoord());
                    } else {
                        const index = $(`th:contains(${lang['abc63490c815af81276f930216c8d92b']})`, table).index();

                        return villages.map(village => $(`td:eq(${index}) a:first`, village).text().trim().toCoord());
                    }
                } else {
                    return villages;
                }
            }

            const html = await loadOverviewPage();
            let villageArray = getVillages(html);

            if (shouldConsiderPages) {
                const pages = $('.paged-nav-item', html).parent().find('option').length ?
                    $('.paged-nav-item', html).parent().find('option').length - 1 :
                    $('.paged-nav-item', html).length;
                const villagesPerPage = mobileCheck ? 10 : 1000;
                const startingPage = Math.floor(1000 / villagesPerPage);

                for (let page = startingPage; page < pages; page++) {
                    const html = await loadOverviewPage(page);
                    villageArray = villageArray.concat(getVillages(html));
                }
            }

            return villageArray;
        } catch (err) {
            console.error(err);
            UI.ErrorMessage(err.message);
        }
    };

    const processFarmGroupsSequentially = async (farmGroups, farmGroupProcessor) => {
        for (const {groupId, returnTime} of farmGroups) {
            const result = await loadAllFromOverview("combined", groupId);
            farmGroupProcessor(result, returnTime);
        }
    };

    const processRunningCommands = (runningCommandsProcessor) => {
        return loadAllFromOverview("commands", 0, "attack").then(runningCommandsProcessor);
    };

    const processAllPages = function (url, processorFn) {
        let page = (url.match('am_farm') || url.match('scavenge_mass')) ? 0 : -1;
        let wrapFn = function (page, $html) {
            let dnp = determineNextPage(page, $html);

            if (dnp) {
                processorFn($html);
                return processPage(url, dnp, wrapFn);
            } else {
                return processorFn($html);
            }
        };

        return processPage(url, page, wrapFn);
    };

    const getDistance = function (origin, target) {
        let a = origin.toCoord(true).x - target.toCoord(true).x;
        let b = origin.toCoord(true).y - target.toCoord(true).y;

        return Math.hypot(a, b);
    };

    const subtractArrays = function (array1, array2) {
        let result = array1.map((val, i) => {
            return val - array2[i];
        });

        return (result.some(v => v < 0)) ? false : result;
    };

    const getCurrentServerTime = function () {
        let [hour, min, sec, day, month, year] = $('#serverTime').closest('p').text().match(/\d+/g);
        return new Date(year, (month - 1), day, hour, min, sec).getTime();
    };

    const timestampFromString = function (timestr) {
        let d = $('#serverDate').text().split('/').map(x => +x);
        let todayPattern = new RegExp("oggi alle %s".replace('%s', '([\\d+|:]+)')).exec(timestr);
        let tomorrowPattern = new RegExp("domani alle %s".replace('%s', '([\\d+|:]+)')).exec(timestr);
        let yesterdayPattern = new RegExp("ieri alle %s".replace('%s', '([\\d+|:]+)')).exec(timestr);
        let laterDatePattern = new RegExp(window.lang['0cb274c906d622fa8ce524bcfbb7552d'].replace('%1', '([\\d+|\\.]+)').replace('%2', '([\\d+|:]+)')).exec(timestr);
        let t, date;

        if (todayPattern !== null) {
            t = todayPattern[1].split(':');
            date = new Date(d[2], (d[1] - 1), d[0], t[0], t[1], t[2], (t[3] || 0));
        } else if (tomorrowPattern !== null) {
            t = tomorrowPattern[1].split(':');
            date = new Date(d[2], (d[1] - 1), (d[0] + 1), t[0], t[1], t[2], (t[3] || 0));
        } else if (yesterdayPattern !== null) {
            t = yesterdayPattern[1].split(':');
            date = new Date(d[2], (d[1] - 1), (d[0] - 1), t[0], t[1], t[2], (t[3] || 0));
        } else {
            d = (laterDatePattern[1] + d[2]).split('.').map(x => +x);
            t = laterDatePattern[2].split(':');
            date = new Date(d[2], (d[1] - 1), d[0], t[0], t[1], t[2], (t[3] || 0));
        }

        return date.getTime();
    };

    String.prototype.toCoord = function (objectified) {
        let c = (this.match(/\d{1,3}\|\d{1,3}/g) || [false]).pop();
        return (c && objectified) ? {x: c.split('|')[0], y: c.split('|')[1]} : c
    };

    String.prototype.toNumber = function () {
        return parseFloat(this);
    };

    Number.prototype.toNumber = function () {
        return parseFloat(this);
    };

    return {
        getUnitSpeeds,
        processPage,
        processAllPages,
        processRunningCommands,
        getDistance,
        subtractArrays,
        getCurrentServerTime,
        timestampFromString,
        processFarmGroupsSequentially
    };
})();

window.FarmGod.Translation = (function () {
    const msg = {
        nl_NL: {
            missingFeatures: 'Script vereist een premium account en farm assistent!',
            options: {
                title: 'FarmGod Opties',
                warning: '<b>Waarschuwingen:</b><br>- Zorg dat A is ingesteld als je standaard microfarm en B als een grotere microfarm<br>- Zorg dat de farm filters correct zijn ingesteld voor je het script gebruikt',
                filterImage: 'https://toxicdonut.dev:8080/img/filterImage_nl.png',
                group: 'Uit welke groep moet er gefarmd worden:',
                distance: 'Maximaal aantal velden dat farms mogen lopen:',
                time: 'Hoe veel tijd in minuten moet er tussen farms zitten:',
                return: 'Maximum tijd waarop farms terug thuis moeten zijn:',
                wall: 'Maximum muur level (indien bekend):',
                losses: 'Verstuur farm naar dorpen met gedeeltelijke verliezen:',
                maxloot: 'Verstuur een B farm als de buit vorige keer vol was:',
                newbarbs: 'Voeg nieuwe barbarendorpen toe om te farmen:',
                button: 'Plan farms'
            },
            table: {
                noFarmsPlanned: 'Er kunnen met de opgegeven instellingen geen farms verstuurd worden.',
                origin: 'Oorsprong',
                target: 'Doel',
                fields: 'Velden',
                farm: 'Farm',
                goTo: 'Ga naar'
            },
            messages: {
                villageChanged: 'Succesvol van dorp veranderd!',
                villageError: 'Alle farms voor het huidige dorp zijn reeds verstuurd!',
                sendError: 'Error: farm niet verstuurd!'
            }
        },
        int: {
            missingFeatures: 'Script requires a premium account and loot assistent!',
            options: {
                title: 'FarmGod Options',
                warning: '<b>Warning:</b><br>- Make sure A is set as your default microfarm and B as a larger microfarm<br>- Make sure the farm filters are set correctly before using the script',
                filterImage: 'https://swtools.be/FarmGod/images/filterImage_int.png',
                group: 'Send farms from group:',
                distance: 'Maximum fields for farms:',
                time: 'How much time in minutes should there be between farms:',
                return: 'Maximum time by which farms must be returned:',
                wall: 'Maximum wall level (if known):',
                losses: 'Send farm to villages with partial losses:',
                maxloot: 'Send a B farm if the last loot was full:',
                newbarbs: 'Add new barbs te farm:',
                button: 'Plan farms'
            },
            table: {
                noFarmsPlanned: 'No farms can be sent with the specified settings.',
                origin: 'Origin',
                target: 'Target',
                fields: 'fields',
                farm: 'Farm',
                goTo: 'Go to'
            },
            messages: {
                villageChanged: 'Successfully changed village!',
                villageError: 'All farms for the current village have been sent!',
                sendError: 'Error: farm not send!'
            }
        }
    };

    const get = function () {
        let lang = (msg.hasOwnProperty(game_data.locale)) ? game_data.locale : 'int';
        return msg[lang];
    };

    return {
        get
    };
})();

window.FarmGod.Main = (function (Library, Translation) {
    const lib = Library;
    const t = Translation.get();
    let curVillage = null;
    let farmBusy = false;

    const init = function () {
        if (game_data.features.Premium.active && game_data.features.FarmAssistent.active) {
            if (game_data.screen == 'am_farm') {
                let options = JSON.parse(localStorage.getItem(farmGodKey)) || {
                    optionGroup: 0,
                    farmGroups: [
                        {
                            groupId: 0,
                            returnTime: ""
                        }
                    ],
                    optionDistance: 25,
                    optionTime: 10,
                    optionReturn: '',
                    optionWall: 0,
                    optionLosses: false,
                    optionMaxloot: true,
                    optionNewbarbs: true
                };

                $.when(buildOptions(options)).then((html) => {
                    Dialog.show('FarmGod', html);

                    $('.clearOptionReturn').off('click').on('click', function ({target}) {
                        const $target = $(target);
                        const index = $target.closest("tr").index();
                        $target.closest("tr").find(".optionReturn").val("");

                        options.farmGroups[index] = {...options.farmGroups[index], returnTime: ""};
                        localStorage.setItem(farmGodKey, JSON.stringify(options));
                    });

                    $(document).off("input change", ".settingsChange")
                        .on("input change", ".settingsChange", ({target}) => {
                            const $target = $(target);
                            const key = $target.data("key");
                            const value = $target.val();
                            const index = $target.closest("tr").index();

                            options.farmGroups[index] = {...options.farmGroups[index], [key]: value};

                            localStorage.setItem(farmGodKey, JSON.stringify(options));
                        });

                    $('.optionButton').off('click').on('click', () => {
                        const farmGroups = $(".farm_group").get().map(group => {
                            const groupId = parseInt($(".optionGroup", group).val());
                            const returnTime = $(".optionReturn", group).val();

                            return {groupId, returnTime};
                        });

                        let errors = false;
                        farmGroups.reduce((acc, {groupId}) => {
                            if (acc[groupId] !== undefined) {
                                errors = true;
                            } else {
                                acc[groupId] = 0;
                            }
                            return acc;
                        }, {});

                        if (errors) {
                            return UI.ErrorMessage("All selected groups should be unique");
                        }

                        let optionDistance = parseFloat($('.optionDistance').val());
                        let optionTime = parseFloat($('.optionTime').val());
                        let optionWall = parseFloat($('.optionWall').val());
                        let optionLosses = $('.optionLosses').prop('checked');
                        let optionMaxloot = $('.optionMaxloot').prop('checked');
                        let optionNewbarbs = $('.optionNewbarbs').prop('checked') || false;

                        if (farmGroups.length > 0) {
                            localStorage.setItem(farmGodKey, JSON.stringify({
                                ...options,
                                optionDistance: optionDistance,
                                optionTime: optionTime,
                                optionWall: optionWall,
                                optionLosses: optionLosses,
                                optionMaxloot: optionMaxloot,
                                optionNewbarbs: optionNewbarbs,
                                farmGroups: farmGroups
                            }));

                            $('.optionsContent').html(UI.Throbber[0].outerHTML + '<br><br>');
                            const sortedFarmGroups = farmGroups.sort((a, b) => {
                                return new Date(a.returnTime) || 0 - new Date(b.returnTime) || 0;
                            });
                            getData(sortedFarmGroups, optionNewbarbs, optionLosses, optionWall).then((data) => {
                                Dialog.close();

                                let plan = createPlanning(optionDistance, optionTime, optionMaxloot, data);
                                $('.farmGodContent').remove();
                                $('#am_widget_Farm').first().before(buildTable(plan.farms));

                                bindEventHandlers();
                                UI.InitProgressBars();
                                UI.updateProgressBar($('#FarmGodProgessbar'), 0, plan.counter);
                                $('#FarmGodProgessbar').data('current', 0).data('max', plan.counter);
                            });
                        } else {
                            return UI.ErrorMessage("No valid farm groups found.");
                        }
                    });
                });
            } else {
                location.href = game_data.link_base_pure + 'am_farm';
            }
        } else {
            UI.ErrorMessage(t.missingFeatures);
        }
    };

    const bindEventHandlers = function () {
        const {market} = game_data;
        $('.farmGod_icon').off('click').on('click', function () {
            if (market != 'nl' || $(this).data('origin') == curVillage) {
                sendFarm($(this));
            } else {
                UI.ErrorMessage(t.messages.villageError);
            }
        });

        $(document).off('keydown').on('keydown', (event) => {
            if ((event.keyCode || event.which) == 13) {
                $('.farmGod_icon').first().trigger('click');
            }
        });

        $('.switchVillage').off('click').on('click', function () {
            curVillage = $(this).data('id');
            UI.SuccessMessage(t.messages.villageChanged);
            $(this).closest('tr').remove();
        });
    };

    const getGroupSelect = (groups, groupId) => {
        let html = `<select class="optionGroup settingsChange" data-key="groupId">`;

        groups.forEach(({type, group_id, name}) => {
            if (type === "separator") {
                html += `<option disabled=""/>`;
            } else {
                html += `<option value="${group_id}" ${(parseInt(group_id) === parseInt(groupId)) ? 'selected' : ''}>${name}</option>`;
            }
        });

        html += `</select>`;

        return html;
    };

    const addFarmOption = (groupId, returnTime, groups, index = 0) => {
        const tdStyle = mobileCheck
            ? "display: flex; flex-direction: column;"
            : "display: flex; align-items: center;";
        const divStyle = mobileCheck
            ? "gap: 8px; justify-content: center;"
            : "gap: 2px; align-items: center;";

        return `<tr class="farm_group">
                <td>${index === 0 ? t.options.group : ""}</td>
                <td style="${tdStyle}">
                        ${getGroupSelect(groups, groupId)}
                        <input type="datetime-local" class="optionReturn settingsChange" data-key="returnTime" value="${returnTime}">
                    <div style="display: flex; ${divStyle}">
                        <input type="button" class="clearOptionReturn" value="X">
                        <img class="add_farm_group" style="width: 16px; cursor: pointer;" 
                            src="https://toxicdonut.dev:8080/img/add.png">
                        ${index > 0
            ? `<img class="remove_farm_group" style="width: 16px; cursor: pointer;" 
                                src="https://toxicdonut.dev:8080/img/remove.png">`
            : ""}
                    </div>
                </td>
            </tr>`;
    };


    const buildOptions = function (options) {
        let checkboxSettings = [false, true, true, true, false];
        let checkboxError = $('#plunder_list_filters').find('input[type="checkbox"]').map((i, el) => {
            return ($(el).prop('checked') != checkboxSettings[i]);
        }).get().includes(true);
        let $templateRows = $('form[action*="action=edit_all"]').find('input[type="hidden"][name*="template"]').closest('tr');
        let templateError = $templateRows.first().find('td').last().text().replace('.', '').toNumber() >= $templateRows.last().find('td').last().text().replace('.', '').toNumber();

        return $.when(getGroups()).then((groups) => {
            $(document).off("click", ".add_farm_group")
                .on("click", ".add_farm_group", () => {
                    const farmGroups = $(".farm_group:last");
                    farmGroups.after(addFarmOption(0, "", groups, farmGroups.length + 1));
                    options.farmGroups.push({groupId: 0, returnTime: ""});
                    localStorage.setItem(farmGodKey, JSON.stringify(options));
                });

            $(document).off("click", ".remove_farm_group")
                .on("click", ".remove_farm_group", ({target}) => {
                    const groupIndex = $(target).closest("tr").index();
                    $(target).closest("tr").remove();
                    options.farmGroups.splice(groupIndex, 1);
                    localStorage.setItem(farmGodKey, JSON.stringify(options));
                });


            return `<style>#popup_box_FarmGod{text-align:center;width:750px;}</style>
                <h3>${t.options.title}</h3><br><div class="optionsContent">
                ${(checkboxError || templateError) ? `<div class="info_box" style="line-height: 15px;font-size:10px;text-align:left;"><p style="margin:0px 5px;">${t.options.warning}<br><img src="${t.options.filterImage}" style="width:100%;"></p></div><br>` : ``}
                <div style="width:90%;margin:auto;background: url(\'graphic/index/main_bg.jpg\') 100% 0% #E3D5B3;border: 1px solid #7D510F;border-collapse: separate !important;border-spacing: 0px !important;"><table class="vis" style="width:100%;text-align:left;font-size:11px;">
                  ${options.farmGroups.map(({groupId, returnTime}, index) => addFarmOption(groupId, returnTime, groups, index)).join("")}
                  <tr><td>${t.options.distance}</td><td><input type="text" size="5" class="optionDistance" value="${options.optionDistance}"></td></tr>
                  <tr><td>${t.options.time}</td><td><input type="text" size="5" class="optionTime" value="${options.optionTime}"></td></tr>
                  <tr><td>${t.options.wall}</td><td><input type="text" size="5" class="optionWall" value="${options.optionWall}"></td></tr>
                  <tr><td>${t.options.losses}</td><td><input type="checkbox" class="optionLosses" ${(options.optionLosses) ? 'checked' : ''}></td></tr>
                  <tr><td>${t.options.maxloot}</td><td><input type="checkbox" class="optionMaxloot" ${(options.optionMaxloot) ? 'checked' : ''}></td></tr>
                  <tr><td>${t.options.newbarbs}</td><td><input type="checkbox" class="optionNewbarbs" ${(options.optionNewbarbs) ? 'checked' : ''}></td></tr>
                </table></div><br><input type="button" class="btn optionButton" value="${t.options.button}"></div>`;
        });
    };

    const getGroups = function () {
        return $.get(TribalWars.buildURL('GET', 'groups', {'ajax': 'load_group_menu'})).then((groups) => groups.result);
    };

    const buildTable = function (plan) {
        let html = `<div class="vis farmGodContent"><h4>FarmGod</h4><table class="vis" width="100%">
                <tr><div id="FarmGodProgessbar" class="progress-bar live-progress-bar progress-bar-alive" style="width:98%;margin:5px auto;"><div style="background: rgb(146, 194, 0);"></div><span class="label" style="margin-top:0px;"></span></div></tr>
                <tr><th style="text-align:center;">${t.table.origin}</th><th style="text-align:center;">${t.table.target}</th><th style="text-align:center;">${t.table.fields}</th><th style="text-align:center;">${t.table.farm}</th></tr>`;

        if (!$.isEmptyObject(plan)) {
            const {market, link_base_pure} = game_data;
            for (let prop in plan) {
                if (market === 'nl') {
                    html += `<tr><td colspan="4" style="background: #e7d098;"><input type="button" class="btn switchVillage" data-id="${plan[prop][0].origin.id}" value="${t.table.goTo} ${plan[prop][0].origin.name} (${plan[prop][0].origin.coord})" style="float:right;"></td></tr>`;
                }

                plan[prop].forEach((val, i) => {
                    html += `<tr class="farmRow row_${(i % 2 == 0) ? 'a' : 'b'}">
                    <td style="text-align:center;"><a href="${link_base_pure}info_village&id=${val.origin.id}">${val.origin.name} (${val.origin.coord})</a></td>
                    <td style="text-align:center;"><a href="${link_base_pure}info_village&id=${val.target.id}">${val.target.coord}</a></td>
                    <td style="text-align:center;">${val.fields.toFixed(2)}</td>
                    <td style="text-align:center;"><a href="#" data-origin="${val.origin.id}" data-target="${val.target.id}" data-template="${val.template.id}" class="farmGod_icon farm_icon farm_icon_${val.template.name}" style="margin:auto;"></a></td>
                  </tr>`;
                });
            }
        } else {
            html += `<tr><td colspan="4" style="text-align: center;">${t.table.noFarmsPlanned}</td></tr>`;
        }

        html += `</table></div>`;

        return html;
    };

    const getData = function (farmGroups, newbarbs, losses, wall) {
        let data = {villages: {}, commands: {}, farms: {templates: {}, farms: {}}};

        let villagesProcessor = (villages, returnTime) => {
            const returnTimestamp = new Date(returnTime).getTime() || 0;
            let skipUnits = ['ram', 'catapult', 'snob', 'militia'];

            villages.map(el => {
                let $el = $(el);
                let $qel = $el.find('.quickedit-label').first();
                let units = [];
                const {units: gameUnits} = game_data;

                if ($('#mobileHeader').length) {
                    gameUnits.forEach((unit) => {
                        if (skipUnits.indexOf(unit) == -1) {
                            let $img = $el.find('img[src*="unit/unit_' + unit + '"]');
                            units.push(($img.length) ? $img.closest('div').text().trim().toNumber() : 0);
                        }
                    });
                } else {
                    units = $el.find('.unit-item').filter((index, element) => {
                        return skipUnits.indexOf(gameUnits[index]) == -1;
                    }).map((index, element) => {
                        return $(element).text().toNumber();
                    }).get();
                }
                const villageCoord = $qel.text().toCoord();

                if (data.villages[villageCoord] && (data.villages[villageCoord].returnTime === 0 || data.villages[villageCoord].returnTime > returnTimestamp)) {
                    data.villages[villageCoord].returnTime = returnTimestamp;
                } else if (!data.villages[villageCoord]) {
                    data.villages[villageCoord] = {
                        "name": $qel.data('text'),
                        "id": parseInt($el.find('.quickedit-vn').first().data('id')),
                        "units": units,
                        "returnTime": returnTimestamp
                    }
                }

                return data.villages[villageCoord];
            });

            return data;
        };

        let commandsProcessor = (villages) => {
            villages.map(el => {
                let $el = $(el);
                let coord = $el.find('.quickedit-label').first().text().toCoord();

                if (coord) {
                    if (!data.commands.hasOwnProperty(coord)) data.commands[coord] = [];
                    return data.commands[coord].push(Math.round(lib.timestampFromString($el.find('td').eq(2).text().trim()) / 1000));
                }
            });

            return data;
        };

        let farmProcessor = ($html) => {
            if ($.isEmptyObject(data.farms.templates)) {
                let unitSpeeds = lib.getUnitSpeeds();

                $html.find('form[action*="action=edit_all"]').find('input[type="hidden"][name*="template"]').closest('tr').map((i, el) => {
                    let $el = $(el);

                    return data.farms.templates[$el.prev('tr').find('a.farm_icon').first().attr('class').match(/farm_icon_(.*)\s/)[1]] = {
                        'id': $el.find('input[type="hidden"][name*="template"][name*="[id]"]').first().val().toNumber(),
                        'units': $el.find('input[type="text"], input[type="number"]').map((index, element) => {
                            return $(element).val().toNumber();
                        }).get(),
                        'speed': Math.max(...$el.find('input[type="text"], input[type="number"]').map((index, element) => {
                            return ($(element).val().toNumber() > 0) ? unitSpeeds[$(element).attr('name').trim().split('[')[0]] : 0;
                        }).get())
                    };
                });
            }

            $html.find('#plunder_list').find('tr[id^="village_"]').map((i, el) => {
                let $el = $(el);
                const villageCoord = $el.find('a[href*="screen=report&mode=all&view="]').first().text().toCoord();
                const currentDateElement = $('#mobileHeader').length > 0 ? $el.next("tr").find("td:first") : $("td:eq(4)", $el);
                const currentArrivalTime = Math.round(lib.timestampFromString(currentDateElement.text().trim()) / 1000);
                if (!data.commands.hasOwnProperty(villageCoord)) data.commands[villageCoord] = [currentArrivalTime];
                else data.commands[villageCoord].push(currentArrivalTime);

                return data.farms.farms[villageCoord] = {
                    'id': $el.attr('id').split('_')[1].toNumber(),
                    'color': $el.find('img[src*="graphic/dots/"]')?.attr('src')?.match(/dots\/(green|yellow|red|blue|red_blue)/)[1] ?? "green",
                    'max_loot': $el.find('img[src*="max_loot/1"]').length > 0,
                    'wall': Number($('td:eq(6)', $el).text().trim().match(/\d+/)?.pop() ?? 0)
                }
            });

            return data;
        };

        let findNewbarbs = () => {
            if (newbarbs) {
                return twLib.get('/map/village.txt').then((allVillages) => {
                    allVillages.match(/[^\r\n]+/g).forEach((villageData) => {
                        let [id, name, x, y, player_id] = villageData.split(',');
                        let coord = `${x}|${y}`;

                        if (Number(player_id) === 0 && !data.farms.farms.hasOwnProperty(coord) && name.includes('Villaggio')) {
                            data.farms.farms[coord] = {
                                'id': id.toNumber()
                            }
                        }
                    });

                    return data;
                });
            } else {
                return data;
            }
        };

        let filterFarms = () => {
            data.farms.farms = Object.fromEntries(Object.entries(data.farms.farms).filter(([key, val]) => {
                return (!val.hasOwnProperty('color')) || (val.wall <= wall && (val.color != 'red') && (val.color != 'red_blue') && (val.color != 'yellow' || losses));
            }));

            return data;
        };

        function logPromiseTime(promise, label) {
            try {
                const start = performance.now();
                return Promise.resolve(promise).then(result => {
                    const end = performance.now();
                    console.log(`${label} took ${end - start}ms`);
                    return result;
                }).catch(async error => {
                    UI.ErrorMessage(error.message);
                    const end = performance.now();
                    console.error(`${label} failed after ${end - start}ms`);
                    throw error;
                });
            } catch (e) {
                throw e;
            }
        }

        return Promise.all([
            logPromiseTime(lib.processFarmGroupsSequentially(farmGroups, villagesProcessor), 'processFarmGroupsSequentially'),
            logPromiseTime(lib.processRunningCommands(commandsProcessor), 'processRunningCommands'),
            logPromiseTime(lib.processAllPages(TribalWars.buildURL('GET', 'am_farm'), farmProcessor), 'processAllPages'),
            logPromiseTime(findNewbarbs(), 'findNewbarbs')
        ]).then(filterFarms).then(() => {
            return data;
        });

    };

    const checkReturnTime = (returnTimestamp) => {
        if (returnTimestamp <= 0) {
            return false;
        } else {
            return returnTimestamp / 1000;
        }
    }

    const createPlanning = function (optionDistance, optionTime, optionMaxloot, data) {
        let plan = {counter: 0, farms: {}};
        let serverTime = Math.round(lib.getCurrentServerTime() / 1000);

        const sortedSourceVillages = Object.entries(data.villages).sort((a, b) => {
            const returnTimeA = a[1].returnTime;
            const returnTimeB = b[1].returnTime;

            if (returnTimeA === 0 && returnTimeB === 0) {
                return 0;
            }
            if (returnTimeA === 0) {
                return 1;
            }
            if (returnTimeB === 0) {
                return -1;
            }
            return returnTimeA - returnTimeB; // Sort by returnTime (ascending)
        });

        for (let x = 0; x < sortedSourceVillages.length; x++) {
            let [sourceCoord, {id, returnTime, units, name}] = sortedSourceVillages[x];

            const optionReturn = checkReturnTime(returnTime);
            const orderedFarms = Object.keys(data.farms.farms).map((key) => {
                return {'coord': key, 'dis': lib.getDistance(sourceCoord, key)};
            }).sort((a, b) => (a.dis > b.dis) ? 1 : -1);

            for (let y = 0; y < orderedFarms.length; y++) {
                const {dis, coord} = orderedFarms[y];
                let farmIndex = data.farms.farms[coord];
                let template_name = (optionMaxloot && farmIndex.hasOwnProperty('max_loot') && farmIndex.max_loot) ? 'b' : 'a';
                let template = data.farms.templates[template_name];
                let unitsLeft = lib.subtractArrays(units, template.units);

                if (!unitsLeft) {
                    break;
                }

                let travelTime = (dis * template.speed) * 60;
                let arrival = Math.round(serverTime + travelTime + Math.round(plan.counter / 5));
                let returnTime = (arrival + travelTime);

                let maxTimeDiff = Math.round(optionTime * 60);
                let timeDiff = true;

                if (data.commands.hasOwnProperty(coord)) {
                    if (!farmIndex.hasOwnProperty('color') && data.commands[coord].length > 0) timeDiff = false;
                    data.commands[coord].forEach((timestamp) => {
                        if (Math.abs(timestamp - arrival) < maxTimeDiff) timeDiff = false;
                    });
                } else {
                    data.commands[coord] = [];
                }
                timeDiff = optionReturn && timeDiff ? returnTime <= optionReturn : timeDiff;

                if (unitsLeft && timeDiff && (dis < optionDistance)) {
                    plan.counter++;
                    if (!plan.farms.hasOwnProperty(sourceCoord)) plan.farms[sourceCoord] = [];

                    plan.farms[sourceCoord].push({
                        'origin': {'coord': sourceCoord, 'name': name, 'id': id},
                        'target': {'coord': coord, 'id': farmIndex.id},
                        'fields': dis,
                        'template': {'name': template_name, 'id': template.id}
                    });

                    units = unitsLeft;
                    data.commands[coord].push(arrival);
                }
            }
        }

        return plan;
    };

    const sendFarm = function ($this) {
        let n = Timing.getElapsedTimeSinceLoad();
        if (!farmBusy && !(Accountmanager.farm.last_click && n - Accountmanager.farm.last_click < 200)) {
            farmBusy = true;
            Accountmanager.farm.last_click = n;
            let $pb = $('#FarmGodProgessbar');

            TribalWars.post(Accountmanager.send_units_link.replace(/village=(\d+)/, 'village=' + $this.data('origin')), null, {
                target: $this.data('target'),
                template_id: $this.data('template'),
                source: $this.data('origin')
            }, function (r) {
                UI.SuccessMessage(r.success);
                $pb.data('current', $pb.data('current') + 1);
                UI.updateProgressBar($pb, $pb.data('current'), $pb.data('max'));
                $this.closest('.farmRow').remove();
                farmBusy = false;
            }, function (r) {
                UI.ErrorMessage(r || t.messages.sendError);
                $pb.data('current', $pb.data('current') + 1);
                UI.updateProgressBar($pb, $pb.data('current'), $pb.data('max'));
                $this.closest('.farmRow').remove();
                farmBusy = false;
            });
        }
    };

    return {
        init
    };
})
(window.FarmGod.Library, window.FarmGod.Translation);

(() => {
    window.FarmGod.Main.init();
})();
    })(window, jQuery, document);
